The following table summarizes the main component classes in the Scitags framework architecture

| Component Class | Role within the SciTags Topography | Prominent Implementations |
| :--- | :--- | :--- |
| [Central Registry](#1-central-registry) | Maintains the globally authoritative mapping of Virtual Organization (VO) names and specific computational activities to standardized numerical SciTag IDs. | [Scitags API](https://scitags.org/api.json) |
| [Data Management Systems (Orchestrators)](#2-data-management-systems-orchestrators) | The origin point of the data transfer intent. These distributed systems possess the required contextual knowledge of exactly why a file is being moved. They formulate the initial SciTag and pass it to the transfer scheduling services. | [Rucio](https://github.com/rucio/rucio), [DIRAC](https://github.com/DIRACGrid/DIRAC), [ALICE O2](https://github.com/AliceO2Group/AliceO2) |
|  [Transfer Services](#3-transfer-services) | Intermediary scheduling brokers that manage the execution queues. They receive the job from the orchestrator and actively push the SciTag metadata to the physical storage nodes during protocol negotiation. | [FTS (File Transfer Service)](https://github.com/cern-fts/fts3), [gfal2](https://github.com/cern-fts/gfal2) |
|  [Storage Systems (Data Transfer Agents)](#4-storage-systems-data-transfer-agents) | The physical server nodes executing the high-throughput disk-to-network input/output operations. They accept the SciTag from the transfer service and must inject it into the network layer via flow services or directly by sending fireflies to collectors. | [XRootD (pmark)](https://github.com/xrootd/xrootd), [dCache](https://github.com/dCache/dcache), [EOS](https://github.com/cern-eos/eos), [StoRM](https://github.com/italiangrid/storm) |
| [Flow Service](#5-flow-services-flowd-go) | Lightweight node-level agents that monitor kernel sockets to emit UDP Fireflies, and optionally, can perform packet marking. This service optional and focuses mainly on R&D. | [flowd-go](https://github.com/scitags/flowd-go) |
| [Collectors](https://github.com/scitags/scitags.github.io/blob/main/collectors.md) | Distributed, big-data aggregation pipelines that ingest, parse, store, and visualize the incoming global telemetry stream. | [firefly-collector](https://github.com/scitags/firefly-collector) | 
| [Dashboards](https://dashboard.stardust.es.net/goto/efsrfifb2kjy8d?orgId=2) | Dashboards showing a global view based on the fireflies collected | [ESnet Dashboard](https://dashboard.stardust.es.net/goto/efsrfifb2kjy8d?orgId=2) |

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
**File Transfer Service (FTS)** support scitags from version 3.2.10 or higher, [gfal2](https://manpages.debian.org/unstable/gfal2-util-scripts/gfal-copy.1.en.html#scitag) library from version 2.21.0 

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
curl -v --insecure -H "SciTag: 313" --capath <ca_path> -s -L -f -u user:password 
     -T /bin/bash https://dest-se.example.org/path/test-file-01
curl -v --insecure -H "SciTag: 313" --capath <ca_path> -s -L -f -u user:password
     -o /tmp/test. https://src.example.org:2881/path/test-file-01
```

### 4. Storage Systems (Data Transfer Agents)
Software executing I/O that performs the physical packet marking or emits "Firefly" packets.

Sample **XRootD/EOS Configuration** (/etc/xrootd/xrootd.cfg; from xrootd 5.0+, [reference docs](https://xrootd.web.cern.ch/doc/dev57/xrd_config.htm#_Toc171719982)):
```bash

# Direct fireflies to a global collector
xrootd.pmark ffdest collector.scitags.org:10514
xrootd.pmark domain remote

# (Optional)
# Fallback configuration to map experiments to directories
# this is only used if there is no information about exp/activity in the protocol (so non-FTS traffic)
# defsfile location default
# note that this is WLCG-specific defsfile location 
xrootd.pmark defsfile curl https://scitags.docs.cern.ch/api.json
# sites not associated with WLCG should use public endpoint at https://scitags.org/api.json

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

Sample **dCache Configuration** (dcache.conf; from dcache 11.2.3+):
```bash
pool.enable.firefly=true
pool.firefly.destination=collector.scitags.org:10514
pool.firefly.storageStatisticsEnabled=true

# (Optional) to exclude local networks
pool.firefly.excludes=a.b.c.d/16, aa:bb:cc:dd:ee:ff/64, v.x.w.z
# Note that dCache will attempt to resolve default VO/activity from FQAN if available
# directory mapping is not available in dCache
```

Sample **StoRM configuration**
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



