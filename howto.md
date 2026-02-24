The following table summarizes the main component classes in the Scitags framework architecture

| Component Class | Role within the SciTags Topography | Prominent Implementations |
| :--- | :--- | :--- |
| **Central Registry** | Maintains the globally authoritative mapping of Virtual Organization (VO) names and specific computational activities to standardized numerical SciTag IDs. | api.scitags.org |
| **Data Management Systems (Orchestrators)** | The origin point of the data transfer intent. These distributed systems possess the required contextual knowledge of exactly why a file is being moved. They formulate the initial SciTag and pass it to the transfer scheduling services. | [Rucio](https://github.com/rucio/rucio), [DIRAC](https://github.com/DIRACGrid/DIRAC), [ALICE O2](https://github.com/AliceO2Group/AliceO2) |
| **Transfer Services** | Intermediary scheduling brokers that manage the execution queues. They receive the job from the orchestrator and actively push the SciTag metadata to the physical storage nodes during protocol negotiation. | [FTS (File Transfer Service)](https://github.com/cern-fts/fts3), [gfal2](https://github.com/cern-fts/gfal2) |
| **Storage Systems (Data Transfer Agents)** | The physical server nodes executing the high-throughput disk-to-network input/output operations. They accept the SciTag from the transfer service and must inject it into the network layer via flow services or directly by sending fireflies to collectors. | [XRootD (pmark)](https://github.com/xrootd/xrootd), [dCache](https://github.com/dCache/dcache), [EOS](https://github.com/cern-eos/eos), [StoRM](https://github.com/italiangrid/storm) |
| **Flow Service** | Lightweight node-level agents that monitor kernel sockets to emit UDP Fireflies, and the  | [flowd-go](https://github.com/scitags/flowd-go) |
| **Collectors** | Distributed, big-data aggregation pipelines that ingest, parse, store, and visualize the incoming global telemetry stream. | [firefly-collector](https://github.com/scitags/firefly-collector) | 

### 1. Central Registry
The source of truth that maps scientific domains/experiments (e.g., ATLAS, CMS) and their specific activities to standardized integer IDs.

```json
{
  "experiments": [
    {"name": "ATLAS", "exp_id": 1},
    {"name": "CMS", "exp_id": 2}
  ],
  "activities": [
    {"name": "Data Consolidation", "activity_id": 4},
    {"name": "Production", "activity_id": 5}
  ]
}
```

### 2. Data Management Systems (Orchestrators)
TBA 

### 3. Transfer Services
Brokers that receive the job and propagate metadata via headers or protocol parameters.
File Transfer Service (FTS) support scitags from version 3.2.10 or higher, [gfal2](https://manpages.debian.org/unstable/gfal2-util-scripts/gfal-copy.1.en.html#scitag) library from version 2.21.0 

```
In all the following examples scitag is an integer calculated using the following bit operations: 
scitag = expID <<6| actID where expID and actID are relevant IDs from registry
```

Sample **FTS** submissions:
```bash
From the command line
$ fts-rest-transfer-submit --scitag <scitag> -s <fts-endpoint> <src> <dst>

From the Python module
import fts3.rest.client.easy as fts3

fts3.new_transfer(.., scitag=<scitag>, ..)

Via the REST API (JSON format)
{
  "files": [
    {
      "sources": [ "<src>" ],
      "destinations": [ "<dst>" ],
      "scitag": 65  # must be integer type
    }
  ],
  "params": {
    "key": "value"
  }
}
```

Sample **gfal-copy** command:
```bash
# Transferring a file with SciTag 132 (e.g., CMS Analysis)
gfal-copy --scitag 132 \
          https://src-ce.example.org/path/to/source.dat \
          https://dest-se.example.org/path/to/destination.dat
```

Sample **xrdcp** command:
```bash
xrdcp https://scr-ce.example.org/path/to/source.dat&scitag.flow=132 /dev/null
```

Sample **curl** command:
```bash
curl -v --insecure -H "SciTag: 313" --capath <ca_path> -s -L -f -u user:password -T /bin/bash https://dest-se.example.org/path/test-file-01
curl -v --insecure -H "SciTag: 313" --capath <ca_path> -s -L -f -u root:password -o /tmp/test. https://src.example.org:2881/path/test-file-01
```

### 4. Storage Systems (Data Transfer Agents)
Software executing I/O that performs the physical packet marking or emits "Firefly" packets.

Sample **XRootD/EOS Configuration** (/etc/xrootd/xrootd.cfg):
```bash

# Direct fireflies to a global collector
xrootd.pmark ffdest collector.scitags.org:10514
xrootd.pmark domain any

# (Optional)
# Fallback configuration to map experiments to directories
# this is only used if there is no information about exp/activity in the protocol (so non-FTS traffic)
# defsfile location default
# note that WLCG-specific defsfile location is different - please consult relevant experiment documentation
xrootd.pmark defsfile curl https://scitags.org/api.json
# multiple entries to map directory to VO (only VO listed in defsfile can be used)
xrootd.pmark map2exp path /<path> <VO>
# xrootd.pmark map2exp path /cephfs/experiments/ska ska

# (Optional)
# if none of the above matches then a default VO and activity can be defined
xrootd.pmark map2exp default <vo>
# rootd.pmark map2exp default ska
xrootd.pmark map2act <vo> default default
# xrootd.pmark map2act ska default default
```

Sample **dCache Configuration** (dcache.conf):
```bash
pool.enable.firefly=true
pool.firefly.destination=collector.scitags.org:10514

# (Optional) to enable storage statistics in fireflies
pool.firefly.storageStatisticsEnabled=true
# (Optional) to exclude local networks
pool.firefly.excludes=a.b.c.d/16, aa:bb:cc:dd:ee:ff/64, v.x.w.z
# Note that dCache will attempt to resolve default VO/activity from FQAN if available
# directory mapping is not available in dCache
```

Sample *StoRM configuration*
TBA

### 5. Flow Services (flowd-go)
Lightweight agents monitoring sockets to assist in telemetry emission.

Sample flowd-go config (conf.json):

```json
{
  "settings": {
    "plugin": "",
    "backends": ["udp_firefly"],
    "flow_map_api": "https://scitags.org/api.json"
  },
  "firefly": {
    "collector_host": "collector.scitags.org",
    "collector_port": 10514
  }
}
```

### 6. Firefly Collectors
The aggregation layer that ingests UDP Firefly packets for visualization and analysis.

Various logstash filters are available that can be added in the logstash pipeline. A sample testing/debugging setup with Opensearch would involve the following:

```
sample setup with logstash
# git clone https://github.com/scitags/firefly-collector.git
# cd firefly-collector
## the provided filters can be composed to perform various different functions
# ll firefly-collector/conf/logstash
total 44
-rw-r--r--. 1 root root  186 Dec 18 10:16 01-input.conf
-rw-r--r--. 1 root root 1193 Dec 18 10:16 02-parsing.conf
-rw-r--r--. 1 root root  421 Dec 18 10:16 05-calc-duration.conf
-rw-r--r--. 1 root root  421 Dec 18 10:18 06-calc-throughput.conf
-rw-r--r--. 1 root root 2552 Dec 18 10:18 63-post-processing.conf
-rw-r--r--. 1 root root 1488 Dec 18 10:16 70-cric-sites.conf
-rw-r--r--. 1 root root  987 Dec 18 10:16 71-scitags.conf
-rw-r--r--. 1 root root  144 Dec 18 10:16 98-stdout.conf.debug
-rw-r--r--. 1 root root  161 Dec 18 10:16 99-firefly-fwd.conf.example
-rw-r--r--. 1 root root  280 Dec 18 10:16 99-opensearch.conf.example
-rw-r--r--. 1 root root 1201 Dec 18 10:16 99-outputs.conf.example

Simple forwarding can be achieved by keeping only 01-input, 02-parsing and 99-firefly-fwd.conf

For a site collector one possible option is to run two independent logstash instances:
# forwarder - collects all fireflies from a site and forwards them to two destinations: collector.scitags.org and local_site_collector
            - this can be achieved by using 01-input, 02-parsing and then two copies of 99-firefly-fwd (one for collector.scitags.org, the other for local_site_collector)
            - note that in this case site storage needs to be reconfigured to send fireflies to the forwarder
# local_site_collector - uses the following filters 01-input, 02-parsing, 05-calc-duration, 06-calc-throughput and 99-opensearch
            - optionally can use 70-cric-sites and 71-scitags to enrich existing data, both require to be initiated via scripts found in metadata/cric and metadata/scitags
            - output files must be shared with logstash container (via conf/logstash_data)

# logstash collector can be run from github repo directory via:
docker run  --network=host --name firefly-stream -d  -v ./conf/logstash/:/usr/share/logstash/pipeline/
            -v ./conf/ruby/:/usr/lib/firefly/ruby/ -v ./conf/logstash_data/:/etc/stardust/pipeline/  
            -t -e XPACK_MONITORING_ENABLED=false -v ./docker-entrypoint:/usr/local/bin/docker-entrypoint docker.elastic.co/logstash/logstash:7.17.19

# Sample Grafana dashboard that works with Opensearch and data enriched with cric and scitags is stored in firefly-collector/dashboards/Scitags Network Flows - OpenSearch.json
```

```
sample docker-compose.yml to run Opensearch in 2 containers (only accessible via localhost)

services:
  opensearch-node: # This is also the hostname of the container within the Docker network (i.e. https://opensearch-node1/)
    image: opensearchproject/opensearch:latest # Specifying the latest available image - modify if you want a specific version
    container_name: opensearch-node
    environment:
      - cluster.name=opensearch-cluster # Name the cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true # Disable JVM heap memory swapping
      - "OPENSEARCH_JAVA_OPTS=-Xms64g -Xmx64g" # Set min and max JVM heap sizes to at least 50% of system RAM
      - OPENSEARCH_INITIAL_ADMIN_PASSWORD=${OPENSEARCH_INITIAL_ADMIN_PASSWORD}    # Sets the demo admin user password when using demo configuration, required for OpenSearch 2.12 and later
      - "DISABLE_INSTALL_DEMO_CONFIG=true" # Prevents execution of bundled demo script which installs demo certificates and security configurations to OpenSearch
      - "DISABLE_SECURITY_PLUGIN=true"
    ulimits:
      memlock:
        soft: -1 # Set memlock to unlimited (no soft or hard limit)
        hard: -1
      nofile:
        soft: 65536 # Maximum number of open files for the opensearch user - set to at least 65536
        hard: 65536
    volumes:
      - /opt/opensearch/vol:/usr/share/opensearch/data # Creates volume called opensearch-data1 and mounts it to the container
    ports:
      - 9200:9200 # REST API
      - 9600:9600 # Performance Analyzer
    network_mode: 'host'
    privileged: true
  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:latest # Make sure the version of opensearch-dashboards matches the version of opensearch installed on other nodes
    container_name: opensearch-dashboard
    depends: opensearch-node
    ports:
      - 5601:5601 # Map host port 5601 to container port 5601
    environment:
      - 'OPENSEARCH_HOSTS: ["http://localhost:9200"]' # Define the OpenSearch nodes that OpenSearch Dashboards will query
      - "DISABLE_SECURITY_DASHBOARDS_PLUGIN=true"
    network_mode: 'host'
```

