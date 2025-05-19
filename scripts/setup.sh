#!/bin/bash

sudo docker network create merope-net

cd ~/merope

cd modules/scanner && sudo docker build -t merope-scanner .
cd ../data_processor && sudo docker build -t merope-data-processor .
cd ../model_engine && sudo docker build -t merope-model-engine .
cd ../nlp_explainer && sudo docker build -t merope-nlp-explainer .
cd ../alert_system && sudo docker build -t merope-alert-system .
cd ../db_layer && sudo docker build -t merope-db-layer .
cd ../api_layer && sudo docker build -t merope-api-layer .
cd ../rabbitmq && sudo docker build -t merope-rabbit:3.13 .

