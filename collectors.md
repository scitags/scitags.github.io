# Firefly Collector Guide

## Table of Contents

- [Overview](#overview)
- [Pipeline Flow](#pipeline-flow)
- [Components](#components)
  - [1. Input (`01-input.conf`)](#1-input-01-inputconf)
  - [2. Parsing (`02-parsing.conf`)](#2-parsing-02-parsingconf)
  - [3. Duration Calculation (`05-calc-duration.conf`)](#3-duration-calculation-05-calc-durationconf)
  - [4. Throughput Calculation (`06-calc-throughput.conf`)](#4-throughput-calculation-06-calc-throughputconf)
  - [5. Post-Processing (`63-post-processing.conf`)](#5-post-processing-63-post-processingconf)
  - [6. Local Traffic Filtering (`64-drop-local.conf`)](#6-local-traffic-filtering-64-drop-localconf)
  - [7. CRIC Site Enrichment (`70-cric-sites.conf`)](#7-cric-site-enrichment-70-cric-sitesconf)
  - [8. SciTags Experiment/Activity Enrichment (`71-scitags.conf`)](#8-scitags-experimentactivity-enrichment-71-scitagsconf)
- [Metadata Generation Scripts](#metadata-generation-scripts)
- [Output Options](#output-options)
- [Sample Deployment Configurations](#sample-deployment-configurations)
- [Logstash Deployment](#docker-deployment)
- [Dashboard](#dashboard)
- [Field Reference](#field-reference)

## Overview

The Firefly Collector is a packet collection and analysis pipeline for any scientific data transfer system that supports fireflies (network telemetry). It ingests network flow metadata via UDP using the "firefly" protocol, enriches the data with site and experiment information, performs calculations, and stores the results for visualization and analysis.

### Pipeline Flow

```
UDP (port 10514) → Logstash → [Parsing → Calculations → Enrichment → Output]
```

## Components

### 1. Input (`01-input.conf`)

Receives firefly packets via UDP on port 10514.

**Key settings:**
- `port => 10514` - Standard firefly UDP port
- `host => "::"` - Listen on all IPv6 interfaces (dual-stack capable)
- `queue_size => 50000` - Input queue depth for burst handling
- `workers => 20` - Parallel packet processing workers

**Configuration tip:** Change `host => "0.0.0.0"` for IPv4-only deployments.

### 2. Parsing (`02-parsing.conf`)

Parses syslog-wrapped firefly packets and extracts the JSON payload.

**What it does:**
- Grok pattern parses the syslog header (priority, version, timestamp, hostname, program, process_id, message_id, structured_data)
- JSON filter extracts the firefly payload from `syslog_message`
- SHA256 fingerprint generates a 5-tuple flow identifier (src_ip, dst_ip, src_port, dst_port, protocol)
- Date filter maps the UNIX_MS timestamp to `@timestamp`

**Output fields after parsing:**
- `[flow-id]` - 5-tuple flow identifier
- `[flow_fingerprint]` - SHA256 hash of the 5-tuple
- `[timestamp]` - Unix timestamp in milliseconds
- Various syslog fields

### 3. Duration Calculation (`05-calc-duration.conf`)

Computes flow duration from start/end timestamps using a Ruby filter.

**Ruby script:** `conf/ruby/calc_duration.rb`

**Logic:**
- Parses `[flow-lifecycle][start-time]` and `[flow-lifecycle][end-time]`
- Calculates: `duration = end_time - start_time`
- Result stored in `[flow-lifecycle][duration]` (rounded to 3 decimal places)

**Requirements:** Both `start-time` and `end-time` must be present and valid ISO8601 format.

### 4. Throughput Calculation (`06-calc-throughput.conf`)

Computes throughput and total bytes for flows with duration data.

**Ruby script:** `conf/ruby/calc_throughput.rb`

**Logic:**
- Uses `duration` from previous filter
- Calculates `usage_bytes = max(received, sent)`
- Calculates `total_bytes = received + sent`
- Calculates `average_throughput = usage_bytes / duration`
- Results stored in `[flow-lifecycle][throughput]` and `[flow-lifecycle][total_bytes]`

**Note:** The `max()` function ensures the larger transfer direction is used for throughput, normalizing direction-agnostic measurements.

### 5. Post-Processing (`63-post-processing.conf`)

Normalizes and renames fields for consistent data model.

**Field renames:**
- `[flow-id]` → `[meta]` namespace (src_port, protocol, src_ip, dst_port, dst_ip)
- Syslog fields → `[meta][syslog]` namespace (timestamp, version, hostname, app_name)
- Context fields → `[meta]` namespace (activity_id, application, experiment_id)
- Firefly version → `[meta][firefly_version]`
- Usage/storage values → `[values]` namespace

**Direction normalization:**
- If `received > sent` and application is NOT http-put/http-get, swaps src/dst fields
- This ensures `sent` is always the larger value for most transfers

**Pruning:** Keeps only essential fields (meta, start, end, duration, throughput, total_bytes, message, @timestamp, values, storage)

**Drop condition:** Events without `[meta][state]` are dropped (incomplete flows)

### 6. Local Traffic Filtering (`64-drop-local.conf`)

Drops traffic where source and destination are at the same site.

**Logic:**
- Uses CRIC site names: `[meta][cric][src][name]` and `[meta][cric][dst][name]`
- Comparison performed after site enrichment in `70-cric-sites.conf`

**Use case:** Eliminates internal network traffic for sites that both ingest and export data.

### 7. CRIC Site Enrichment (`70-cric-sites.conf`)

Enriches flows with WLCG CRIC (Central Resource Investigation Catalog) metadata.

**Metadata source:** MaxMind DB (`cric.mmdb`) generated by `metadata/cric/cric_metadata_collector.py`

**What it does:**
1. **Source IP lookup** - GeoIP lookup on `[meta][src_ip]` → `[meta][cric][src]`
2. **Destination IP lookup** - GeoIP lookup on `[meta][dst_ip]` → `[meta][cric][dst]`
3. **JSON expansion** - CRIC metadata stored as JSON string in `city_name` is extracted
4. **Hostname resolution** - Resolves `[meta][syslog][hostname]` to IP via DNS, then looks up site info
5. **Site name extraction** - Site name available in `[meta][cric][src][name]`, `[meta][cric][dst][name]`, and `[meta][syslog][geoip][name]`

**DNS caching:**
- `cache_size => 10000` - Caches up to 10,000 hostname-to-IP mappings
- `cache_ttl => 86400` - 24-hour TTL for DNS cache entries

**CRIC metadata includes:**
- `name` - Site name (e.g., "AGLT2")
- `latitude`, `longitude` - Geographic coordinates
- `country` - Country name
- `net_site` - Network site identifier
- `asn` - Autonomous System Number
- `tier` - WLCG tier level (0, 1, 2, or 3)

### 8. SciTags Experiment/Activity Enrichment (`71-scitags.conf`)

Translates experiment and activity IDs to human-readable names.

**Metadata source:** YAML maps generated by `metadata/scitags/scitags_registry_map.py`

**What it does:**
1. **Experiment name lookup** - Translates `experiment_id` → `experiment` using `experiments_map.yml`
2. **Activity name lookup** - Creates composite key (`experimentId_activityId`) → `activity` using `activities_map.yml`

**Output:**
- `[meta][experiment]` - Human-readable experiment name (e.g., "ATLAS")
- `[meta][activity]` - Human-readable activity name (e.g., "Real Data")

## Global Collector Configuration

The global collector configuration includes all available filters in the recommended processing order. This is used when you need full flow analysis with all enrichment data.

```ruby
# Input
01-input.conf

# Parsing
02-parsing.conf

# Calculations
05-calc-duration.conf
06-calc-throughput.conf

# Post-processing (renames, direction normalization, pruning)
63-post-processing.conf

# Local traffic filtering (optional - skip if you want to keep all traffic)
64-drop-local.conf

# Site enrichment (requires cric.mmdb)
70-cric-sites.conf

# Experiment/activity enrichment (requires YAML maps)
71-scitags.conf

# Output (choose one: Opensearch, Kafka, or Forwarding)
99-outputs.conf.example
99-kafka.conf.example
99-firefly-fwd.conf.example
```

**When to use:** Choose this configuration when you need complete flow data with site locations, experiment names, duration, throughput, and all enrichment for analysis, dashboards, and long-term storage.

## Metadata Generation Scripts

### CRIC Metadata Collector (`metadata/cric/cric_metadata_collector.py`)

Generates the `cric.mmdb` database with WLCG CRIC site information.

**Usage:**
```bash
cd metadata/cric
python cric_metadata_collector.py --verbose --output_mmdb /path/to/conf/logstash_data/cric.mmdb
```

**Options:**
- `--cric_url` - Custom CRIC API endpoint (default: WLCG-CRIC)
- `--output_mmdb` - Output file path for MMDB
- `--verbose` - Enable debug logging
- `--periodic N` - Run periodically every N seconds

**Required output path in Logstash:** `/etc/stardust/pipeline/cric.mmdb`

### SciTags Registry Map (`metadata/scitags/scitags_registry_map.py`)

Generates YAML maps for experiment and activity names from the SciTags API.

**Usage:**
```bash
cd metadata/scitags
python scitags_registry_map.py --verbose --output-yaml /path/to/conf/logstash_data
```

**Options:**
- `--scitags_url` - Custom SciTags API endpoint (default: http://scitags.docs.cern.ch/api.json)
- `--output-yaml` - Output directory for YAML files
- `--verbose` - Enable debug logging
- `--periodic N` - Run periodically every N seconds

**Output files:**
- `experiments_map.yml` - Key: experiment ID, Value: experiment name
- `activities_map.yml` - Key: "experimentId_activityId", Value: activity name

**Required paths in Logstash:** `/etc/stardust/pipeline/experiments_map.yml` and `/etc/stardust/pipeline/activities_map.yml`

## Output Options

### Opensearch/Elasticsearch (`99-outputs.conf.example`)

Sends data to Opensearch/Elasticsearch with ILM (Index Lifecycle Management).

**Key settings:**
- ILM enabled with pattern `{now/d}-000001`
- Index alias: `stardust_firefly`
- Requires ILM policy and template prior to launch

**Use case:** When you need long-term storage, search capabilities, and visualization with Kibana/OpenSearch/Grafana Dashboards.

### Forwarding (`99-firefly-fwd.conf.example`)

Forwards raw firefly messages via UDP to another collector.

**Use case:** Site forwarders that collect local fireflies and send to R&E collectors.

### Kafka (`99-kafka.conf.example`)

Sends firefly messages to a Kafka bus for integration with the Research & Education (R&E) collector facility.

**Key settings:**
- `bootstrap_servers` - Kafka broker addresses (comma-separated)
- `topic_id` - Kafka topic for firefly messages
- `acks` - Acknowledgment requirement (0, 1, or all)
- `batch_size` - Number of messages to batch (default: 16384)
- `linger_ms` - Time to wait for batch accumulation (default: 5)

**Use case:** R&E collector facilities connected to other collectors via Kafka bus, enabling decoupled message distribution to multiple consumers, scalable ingestion by downstream systems, and integration with Kafka-based data lakes and stream processing.

## Sample Deployment Configurations

### Minimal Forwarder

**Pipeline:** `01-input.conf` + `02-parsing.conf` + `99-firefly-fwd.conf`

**Description:** Basic configuration that only parses incoming firefly packets and forwards them unchanged to another collector. Use this when you need a simple relay point with minimal processing overhead, such as a local site collector that forwards to a central collector.

### R&E Collector

**Pipeline:** `01-input.conf` + `02-parsing.conf` + `99-kafka.conf.example`

**Description:** Parses fireflies and publishes them to a Kafka bus for integration within R&E network. Use this when you're setting up R&E collector to feed data to a global R&E collector facility.

### Site Forwarder + Local Collector (Two Logstash Instances)

**Forwarder instance:**
- Input + parsing + forwarding to central collector and/or Kafka bus

**Local collector instance:**
- Input + all filters + Opensearch output

**Description:** Full processing pipeline that calculates duration and throughput, enriches data with site locations (CRIC) and experiment names (SciTags), then stores in Opensearch for visualization. Use this at a local site that wants to maintain its own analysis and dashboard capabilities while at the same time forwarding to a central collector. Two separate Logstash instances running on the same site. The forwarder handles quick relay of fireflies to central systems, while the local collector performs full enrichment and storage for site-specific analysis. 

## Logstash Deployment

```bash
docker run \
  --network=host \
  --name firefly-stream \
  -d \
  -v ./conf/logstash/:/usr/share/logstash/pipeline/ \
  -v ./conf/ruby/:/usr/lib/firefly/ruby/ \
  -v ./conf/logstash_data/:/etc/stardust/pipeline/ \
  -e XPACK_MONITORING_ENABLED=false \
  docker.elastic.co/logstash/logstash:7.17.19
```

### Opensearch Deployment (Docker Compose)

This setup is recommended for the *Local/site Collector* configuration where you need a complete stack running on a single site.

```yaml
version: '3'
services:
  opensearch-node:
    image: opensearchproject/opensearch:latest
    environment:
      - cluster.name=opensearch-cluster
      - discovery.type=single-node
      - "OPENSEARCH_JAVA_OPTS=-Xms64g -Xmx64g"
      - "DISABLE_INSTALL_DEMO_CONFIG=true"
      - "DISABLE_SECURITY_PLUGIN=true"
    volumes:
      - /opt/opensearch/vol:/usr/share/opensearch/data
    ports:
      - "9200:9200"
      - "9600:9600"
    network_mode: 'host'
    privileged: true

  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:latest
    depends_on:
      - opensearch-node
    ports:
      - "5601:5601"
    environment:
      - 'OPENSEARCH_HOSTS=["http://localhost:9200"]'
      - "DISABLE_SECURITY_DASHBOARDS_PLUGIN=true"
    network_mode: 'host'
```

## Dashboard

Sample OpenSearch dashboard: `dashboards/Scitags Network Flows - OpenSearch.json`

Supports:
- Site-based filtering (WLCG CRIC sites)
- Experiment filtering (ATLAS, CMS, etc.)
- Activity filtering (Real Data, Simulations, etc.)
- Geographic visualization
- Performance metrics (throughput, duration)

**Note:** The dashboard file is for OpenSearch Dashboards. For Grafana, import the dashboard JSON and configure as a data source.

## Field Reference

### Core Fields (after parsing)

| Field | Description |
|-------|-------------|
| `[meta][id]` | Flow fingerprint (SHA256) |
| `[meta][state]` | Flow lifecycle state |
| `[meta][src_ip]` | Source IP address |
| `[meta][dst_ip]` | Destination IP address |
| `[meta][src_port]` | Source port |
| `[meta][dst_port]` | Destination port |
| `[meta][protocol]` | Protocol (TCP/UDP) |
| `[meta][ip_version]` | IP version (4 or 6) |
| `[meta][application]` | Application name |
| `[meta][experiment_id]` | SciTags experiment ID |
| `[meta][activity_id]` | SciTags activity ID |
| `[meta][firefly_version]` | Firefly protocol version |
| `[start]` | Flow start timestamp |
| `[end]` | Flow end timestamp |
| `[duration]` | Flow duration (seconds) |
| `[throughput]` | Average throughput (bytes/sec) |
| `[total_bytes]` | Total bytes transferred |

### Enriched Fields

| Field | Description |
|-------|-------------|
| `[meta][cric][src][name]` | Source site name |
| `[meta][cric][src][country]` | Source country |
| `[meta][cric][src][latitude]` | Source site latitude |
| `[meta][cric][src][longitude]` | Source site longitude |
| `[meta][cric][dst][name]` | Destination site name |
| `[meta][cric][dst][country]` | Destination country |
| `[meta][cric][dst][latitude]` | Destination site latitude |
| `[meta][cric][dst][longitude]` | Destination site longitude |
| `[meta][experiment]` | Human-readable experiment name |
| `[meta][activity]` | Human-readable activity name |

## Notes

- All Logstash configurations use conditional ordering (01, 02, 05, 06, 63, 70, 71, 99) to ensure proper processing order
- The pipeline requires both `cric.mmdb` and YAML maps for full enrichment functionality
- Site normalization ensures `sent` is the larger value (except for http-put/http-get)
- Local traffic filtering requires site enrichment to be effective
- For the Kafka output, install the Logstash Kafka plugin: `bin/logstash-plugin install logstash-output-kafka`
