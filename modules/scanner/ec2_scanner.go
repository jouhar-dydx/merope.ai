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

type Instance struct {
    ID               string                 `json:"resource_id"`
    Region           string               `json:"region"`
    Service          string               `json:"service"`
    ResourceType     string               `json:"resource_type"`
    ScanID           string               `json:"scan_id"`
    Data             map[string]interface{} `json:"data"`
    Orphaned         bool                 `json:"orphaned"`
    PublicIP         bool                 `json:"public_ip"`
    MissingMetadata  map[string]bool      `json:"missing_metadata"`
    AssociatedResources map[string]interface{} `json:"associated_resources"`
    Timestamp        int64                `json:"timestamp"`
}

var logger *log.Logger

func init() {
    logFile, _ := os.OpenFile("/logs/merope/scanner.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    logger = log.New(logFile, "[EC2Scanner] ", log.LstdFlags)
}

func convertInstance(instance *ec2.Instance) map[string]interface{} {
    m := make(map[string]interface{})
    m["InstanceId"] = instance.InstanceId
    m["State"] = instance.State.Name
    m["PublicIpAddress"] = instance.PublicIpAddress
    m["Tags"] = instance.Tags
    return m
}

func isOrphaned(instance map[string]interface{}) bool {
    tags, ok := instance["Tags"].([]interface{})
    return !ok || len(tags) == 0
}

func scanEC2Instances(scanID string) ([]Instance, error) {
    cfg, _ := config.LoadDefaultConfig(context.TODO())
    svc := ec2.NewFromConfig(cfg)

    input := &ec2.DescribeInstancesInput{}
    paginator := ec2.NewDescribeInstancesPaginator(svc, input)

    var results []Instance

    for paginator.HasMorePages() {
        page, err := paginator.NextPage(context.TODO())
        if err != nil {
            log.Printf("🚨 Error fetching page: %v", err)
            continue
        }

        for _, reservation := range page.Reservations {
            for _, instance := range reservation.Instances {
                instanceMap := convertInstance(instance)

                results = append(results, Instance{
                    ID:              *instance.InstanceId,
                    Region:          *svc.Options().Region,
                    Service:         "ec2",
                    ResourceType:    "instance",
                    ScanID:          scanID,
                    Data:            instanceMap,
                    Orphaned:        isOrphaned(instanceMap),
                    PublicIP:        instance.PublicIpAddress != nil,
                    MissingMetadata: map[string]bool{"tags_missing": isOrphaned(instanceMap)},
                    AssociatedResources: map[string]interface{}{
                        "security_groups": instance.SecurityGroups,
                        "vpc_id":        instance.VpcId,
                    },
                    Timestamp: time.Now().Unix(),
                })

                sendToKafka(results[len(results)-1])
                saveToDisk(*instance.InstanceId, results[len(results)-1])
            }
        }
    }

    return results, nil
}

func saveToDisk(id string, item Instance) {
    os.MkdirAll("/logs/aws_scans/ec2", os.ModePerm)
    jsonData, _ := json.MarshalIndent(item, "", "  ")
    os.WriteFile(fmt.Sprintf("/logs/aws_scans/ec2/%s.json", id), jsonData, 0644)
}

func sendToKafka(item Instance) {
    p, err := kafka.NewProducer(&kafka.ConfigMap{"bootstrap.servers": "kafka:9092"})
    if err != nil {
        log.Fatalf("❌ Failed to create Kafka producer: %v", err)
    }
    defer p.Close()

    jsonData, _ := json.Marshal(item)
    deliveryChan := make(chan kafka.Event)

    err = p.Produce(&kafka.Message{
        TopicPartition: kafka.TopicPartition{Topic: "aws_scan_data", Partition: kafka.PartitionAny},
        Key:            []byte(item.ID),
        Value:          jsonData,
    }, deliveryChan)

    e := <-deliveryChan
    msg := e.(*kafka.Message)
    if msg.TopicPartition.Error != nil {
        log.Printf("❌ Kafka delivery failed: %v", msg.TopicPartition.Error)
    } else {
        log.Printf("✅ Sent %s | Offset: %v", item.ID, msg.TopicPartition.Offset)
    }
    close(deliveryChan)
}

func getActiveRegions(session *ec2.Client) ([]string, error) {
    output, err := session.DescribeRegions(context.TODO(), &ec2.DescribeRegionsInput{})
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

    fmt.Println("📡 Starting Merope AWS Scanner v1.0")
    scanID := fmt.Sprintf("SCAN-%d", time.Now().UnixNano())

    log.Println("🔌 Initializing AWS Session...")
    session := ec2.NewFromConfig(config.LoadDefaultConfig(context.TODO()))

    regions, _ := getActiveRegions(session)
    for _, region := range regions {
        client := ec2.NewFromConfig(config.LoadDefaultConfig(context.TODO(), config.WithRegion(region)))
        fmt.Printf("🌍 Scanning region: %s\n", region)

        scanner := func() ([]Instance, error) {
            return scanEC2Instances(scanID)
        }

        instances, _ := scanner()
        log.Printf("📦 Found %d running EC2 instances in %s\n", len(instances), region)
    }
}
