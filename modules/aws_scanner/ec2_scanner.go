package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "os"
    "time"

    "github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/service/ec2"
    "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// Instance represents the full data structure sent to Kafka
type Instance struct {
    ScanID             string                 `json:"scan_id"`
    Region             string                 `json:"region"`
    Service            string                 `json:"service"`
    ResourceType       string                 `json:"resource_type"`
    ResourceID           string                 `json:"resource_id"`
    Data               map[string]interface{}   `json:"data"`
    Orphaned           bool                   `json:"orphaned"`
    PublicIP           bool                   `json:"public_ip"`
    MissingMetadata    map[string]interface{}   `json:"missing_metadata"`
    AssociatedResources map[string]interface{} `json:"associated_resources"`
    Timestamp          int64                  `json:"timestamp"`
}

// Set up logging
var logger *log.Logger

func init() {
    logFile, err := os.OpenFile("/logs/merope/scanner.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    if err != nil {
        log.Fatalf(" Failed to open log file: %v", err)
    }
    logger = log.New(logFile, "", log.LstdFlags)
    logger.SetPrefix("[EC2Scanner] ")
    logger.SetFlags(0)
}

func getEC2Client(region string) (*ec2.Client, error) {
    cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion(region))
    if err != nil {
        return nil, fmt.Errorf("failed to load AWS config: %v", err)
    }
    return ec2.NewFromConfig(cfg), nil
}

func isOrphaned(instance map[string]interface{}) bool {
    tags, ok := instance["Tags"].([]interface{})
    return !ok || len(tags) == 0
}

func hasPublicIP(instance map[string]interface{}) bool {
    ip, ok := instance["PublicIpAddress"].(string)
    return ok && ip != ""
}

func convertInstance(instance ec2.Instance) map[string]interface{} {
    m := make(map[string]interface{})
    m["InstanceId"] = instance.InstanceId
    m["State"] = instance.State
    m["PublicIpAddress"] = instance.PublicIpAddress
    m["Tags"] = instance.Tags
    m["SecurityGroups"] = instance.SecurityGroups
    m["VpcId"] = instance.VpcId
    m["SubnetId"] = instance.SubnetId
    m["AccountId"] = instance.AccountId
    m["KeyName"] = instance.KeyName
    m["LaunchTime"] = instance.LaunchTime
    m["PlatformDetails"] = instance.PlatformDetails
    return m
}

func scanEC2Instances(scanID string) ([]Instance, error) {
    regions, err := getActiveRegions()
    if err != nil {
        return nil, err
    }

    var allInstances []Instance

    for _, region := range regions {
        client, err := getEC2Client(region)
        if err != nil {
            log.Printf(" Skipping region %s: %v", region, err)
            continue
        }

        input := &ec2.DescribeInstancesInput{}
        paginator := ec2.NewDescribeInstancesPaginator(client, input)

        for paginator.HasMorePages() {
            page, err := paginator.NextPage(context.TODO())
            if err != nil {
                log.Printf(" Error fetching page in %s: %v", region, err)
                continue
            }

            for _, reservation := range page.Reservations {
                for _, instance := range reservation.Instances {
                    instanceMap := convertInstance(*instance)
                    orphaned := isOrphaned(instanceMap)

                    item := Instance{
                        ScanID:       scanID,
                        Region:       region,
                        Service:      "ec2",
                        ResourceType: "instance",
                        ResourceID:   *instance.InstanceId,
                        Data:         instanceMap,
                        Orphaned:     orphaned,
                        PublicIP:     hasPublicIP(instanceMap),
                        MissingMetadata: map[string]interface{}{
                            "tags_missing": orphaned,
                        },
                        AssociatedResources: map[string]interface{}{
                            "security_groups": instanceMap["SecurityGroups"],
                            "vpc_id":        instanceMap["VpcId"],
                        },
                        Timestamp: time.Now().Unix(),
                    }

                    // Save raw scan to file
                    saveInstanceToFile(item)

                    // Add to results
                    allInstances = append(allInstances, item)
                }
            }
        }
    }

    return allInstances, nil
}

func saveInstanceToFile(instance Instance) {
    data, _ := json.MarshalIndent(instance, "", "  ")
    err := os.WriteFile(fmt.Sprintf("/logs/aws_scans/ec2/%s.json", instance.ResourceID), data, 0644)
    if err != nil {
        log.Printf(" Failed to save instance %s to file: %v", instance.ResourceID, err)
    }
}

func sendToKafka(topic string, instances []Instance) {
    p, err := kafka.NewProducer(&kafka.ConfigMap{"bootstrap.servers": "merope-kafka:9092"})
    if err != nil {
        log.Fatalf(" Failed to create Kafka producer: %v", err)
    }
    defer p.Close()

    for _, msg := range instances {
        jsonData, _ := json.Marshal(msg)

        deliveryChan := make(chan kafka.Event)
        err := p.Produce(&kafka.Message{
            TopicPartition: kafka.TopicPartition{Topic: &topic, Partition: kafka.PartitionAny},
            Key:            []byte(msg.ResourceID),
            Value:          jsonData,
        }, deliveryChan)

        if err != nil {
            log.Printf(" Failed to send to Kafka: %v", err)
        } else {
            e := <-deliveryChan
            m := e.(*kafka.Message)
            if m.TopicPartition.Error != nil {
                log.Printf(" Kafka delivery failed: %v", m.TopicPartition.Error)
            } else {
                log.Printf(" Sent to Kafka: %s [%d] at offset %v\n", *m.TopicPartition.Topic, m.TopicPartition.Partition, m.TopicPartition.Offset)
            }
        }
        close(deliveryChan)
    }
}

func getActiveRegions() ([]string, error) {
    cfg, _ := config.LoadDefaultConfig(context.TODO(), config.WithRegion("us-east-1"))
    ec2Client := ec2.NewFromConfig(cfg)

    input := &ec2.DescribeRegionsInput{}
    output, err := ec2Client.DescribeRegions(context.TODO(), input)
    if err != nil {
        return []string{"us-east-1"}, nil
    }

    var regions []string
    for _, r := range output.Regions {
        regions = append(regions, *r.RegionName)
    }

    return regions, nil
}

func main() {
    scanID := fmt.Sprintf("SCAN-%d", time.Now().UnixNano())

    log.Println(" Initializing AWS Session...")
    log.Printf(" Scan ID: %s\n", scanID)

    instances, err := scanEC2Instances(scanID)
    if err != nil {
        log.Printf(" No running instances found")
        return
    }

    log.Printf(" Found %d running EC2 instances\n", len(instances))

    // Send to Kafka
    sendToKafka("aws_scan_data", instances)
}