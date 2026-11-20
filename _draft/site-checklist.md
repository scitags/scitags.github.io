# Site checklist

How to turn on SciTags at a WLCG storage site. It takes four steps and a CRIC check. ATLAS is asking every storage site to enable fireflies before the next WLCG Data Challenge (DC27, early 2027).

## Before you start: your network in CRIC

SciTags works out which site a flow belongs to from its IP addresses, using the network prefixes registered in WLCG CRIC. Today about half of all fireflies cannot be attributed to a site because a prefix is missing, so check this first.

- Register every prefix that hosts WLCG services: storage, FTS endpoints, compute and perfSONAR, including prefixes that are not on LHCONE.
- Your site needs a NetSite with NetworkRoutes that hold its IPv4 and IPv6 prefixes. The Collaborations field must read exactly `WLCG`.
- Editing needs the `SITE_<SITE>_Admin` group, requested at <https://wlcg-cric.cern.ch/core/usergrouprequest/create/>. Without a CERN account, write to lhcone-operations@cern.ch.
- See what is registered now: <https://wlcg-cric.cern.ch/api/core/rcsite/query/?json>

## 1. Run a SciTags-capable version

| Software | Minimum | Notes |
| :--- | :--- | :--- |
| dCache | 11.2.4 | Recommended: the next 11.2 production release with the November 2026 firefly fixes (expected 11.2.12). 11.2.3 sends no start markers for HTTP third-party copies; 10.2 cannot send to a collector. |
| XRootD | 5.0 | |
| EOS | 5.2.19 | Takes its packet-marking settings from XRootD. |
| StoRM | 1.4.3 | Fireflies are sent by flowd-go. Known issues are being investigated; an update is expected in December 2026. |
| FTS | 3.12.11 (FTS-REST 3.12.4) | Passes the tag on to storage. |
| gfal2 | 2.21.0 | |
| Rucio | 32.4.0 | |
| DIRAC | 9.0.8 | |

Rucio, FTS, DIRAC and ALICE O2 already pass the tag to storage in production, so a site only has to configure its storage.

## 2. Turn on fireflies on every data-serving node

Send fireflies to `collector.scitags.org:10514`, unless your network provider asks you to use its own collector. Do not use `global.scitags.org`: it rejected fireflies in September 2026.

### dCache

```
pool.enable.firefly=true
pool.firefly.destination=collector.scitags.org:10514

# Optional: skip fireflies when both endpoints are local
pool.firefly.excludes=a.b.c.d/16, aa:bb:cc:dd:ee:ff/64
```

- Set `pool.firefly.destination`. Without it, dCache sends fireflies only to the other end of the transfer. Several sites missed this when they upgraded. Restart the pools afterwards.
- Pools must talk to the WAN directly. Pools whose WAN traffic goes through the doors produce no useful fireflies.
- Leave `pool.firefly.vo-mapping` at its default unless asked to change it.

### XRootD and EOS

```
xrootd.pmark ffdest collector.scitags.org:10514
xrootd.pmark domain remote

# Optional: fallback for transfers that carry no SciTag
xrootd.pmark defsfile curl https://scitags.docs.cern.ch/api.json
```

- Configure the data servers, not the redirectors.
- Single-VO sites may add `xrootd.pmark map2exp default <vo>`.
- Multi-VO sites must not set `map2exp default`. Map paths to experiments instead, with `xrootd.pmark map2exp path /<path> <vo>` and `xrootd.pmark map2act <vo> default default`.

### StoRM

StoRM hands flow events to flowd-go, which sends the fireflies:

```
plugins:
   namedPipe:
       pipePath: "/var/run/flowd"

backends:
   firefly: {
       stun: {},
       sendToCollector: true,
       collectorAddress: collector.scitags.org
   }
```

## 3. Open the network

- **Outbound:** UDP 10514 to `collector.scitags.org`, over IPv4 and IPv6.
- **Inbound:** nothing.

`collector.scitags.org` points each site at the nearest regional collector: `us.scitags.org` (ESnet), `uk.scitags.org` (Jisc) or `eu.scitags.org` (GÉANT). The regional collectors forward to ESnet. An Asia/Pacific collector is planned.

## 4. Check that it works

1. On a data server, `tcpdump -nn -i any udp port 10514` shows packets going to the collector, with no ICMP "unreachable" replies.
2. Send a test transfer with tag 154 (ATLAS = 2, activity Data Challenge = 26; 2 << 6 | 26 = 154):

        curl -H "SciTag: 154" https://<door>/<path> -o /dev/null
        xrdcp "root://<host>//<path>?scitag.flow=154" /dev/null

3. Within 48 hours your site appears on the [SciTags dashboard](https://dashboard.stardust.es.net/d/b6d7dc1e-dc56-4f39-abe0-a9e7199021f8/scitags-network-flows-v3). Set Source Site or Dest Site to your WLCG site name.
4. If it does not appear, check your CRIC prefixes first: that is the usual cause.

To see what dCache sends, set the `org.dcache.scitags` logger to DEBUG in `logback.xml`, both as a `<logger>` entry and as a threshold in the CellThresholdFilter, then look for `scitags event=marker` and `event=marker-skip` lines.

## Known issues

- **`global.scitags.org`** rejected fireflies in September 2026. Use `collector.scitags.org`.
- **XRootD 5.7** reports flow end times about 10 seconds late. XRootD 5.9 does not.
- **StoRM** firefly issues are under investigation; an update is expected in December 2026.
- **The dashboard** cannot yet show which hosts at a site are sending. A per-host view has been requested, so for now the dashboard alone does not prove that every node is configured.
