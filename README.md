# gtfs2kml - Quick Start & CI/CD Commands

## TL;DR - Most Common Commands

### 1. Basic Conversion (No Road Snapping)
```bash
gtfs2kml ./gtfs_data ./output
```

### 2. With Densification Only (No API Needed)
```bash
gtfs2kml ./gtfs_data ./output --densify-points 100
```

### 3. Production-Ready with Road Snapping (Local OSRM)
```bash
gtfs2kml ./gtfs_data ./output \
  --snap-to-roads \
  --snap-provider osrm \
  --densify-points 100 \
  --snap-cache-dir ./snap_cache \
  --verbose
```

### 4. Single Route Testing
```bash
gtfs2kml ./gtfs_data ./output \
  -r J10CWL \
  --snap-to-roads \
  --snap-provider osrm \
  --densify-points 100 \
  --verbose
```

---

## Production Commands (MyBAS Johor)

```bash
cd /home/lucas/PSD/mybas-johor

# Full production (road snapping + densification)
gtfs2kml/venv/bin/python -m gtfs2kml.cli . ./output_snapped_densified \
  --snap-to-roads \
  --snap-provider osrm \
  --densify-points 100 \
  --snap-cache-dir ./snap_cache \
  --verbose

# Test single route first
gtfs2kml/venv/bin/python -m gtfs2kml.cli . ./test_output \
  -r J10CWL \
  --snap-to-roads \
  --densify-points 100 \
  --snap-cache-dir ./snap_cache \
  --verbose
```

---

## OSRM Local Setup (One-Time)

```bash
# 1. Create data directory
mkdir -p ~/osrm-data && cd ~/osrm-data

# 2. Download OSM data (~227MB)
wget https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf

# 3. Process data (~10 minutes one-time)
docker run -t -v $(pwd):/data ghcr.io/project-osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/malaysia-singapore-brunei-latest.osm.pbf

docker run -t -v $(pwd):/data ghcr.io/project-osrm/osrm-backend \
  osrm-partition /data/malaysia-singapore-brunei-latest.osrm

docker run -t -v $(pwd):/data ghcr.io/project-osrm/osrm-backend \
  osrm-customize /data/malaysia-singapore-brunei-latest.osrm

# 4. Start OSRM server
docker run -d --restart unless-stopped \
  -p 5000:5000 \
  -v $(pwd):/data \
  --name osrm-backend \
  ghcr.io/project-osrm/osrm-backend \
  osrm-routed --algorithm mld /data/malaysia-singapore-brunei-latest.osrm

# 5. Test
curl "http://localhost:5000/route/v1/driving/103.730,1.464;103.760,1.490"
```

### Manage OSRM
```bash
docker ps                      # Check status
docker logs osrm-backend       # View logs
docker stop osrm-backend       # Stop
docker start osrm-backend      # Start
docker restart osrm-backend    # Restart
```

---

## CI/CD Pipeline (GitHub Actions)

```yaml
name: Generate Transit KML

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  generate-kml:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3
      
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install gtfs2kml
        run: |
          pip install requests geopy simplekml click
          cd gtfs2kml && pip install -e .

      - name: Generate KML
        run: |
          gtfs2kml . ./kml_output \
            --densify-points 100 \
            --verbose

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: transit-kml
          path: ./kml_output/*.kml
          retention-days: 90
```

---

## Performance Tuning

### Chunk Size (edit `road_snapper.py`)

```python
# Best quality (recommended)
OSRM_CHUNK_SIZE = 6   # ~1000 API calls, ~10s, excellent confidence

# Balanced
OSRM_CHUNK_SIZE = 10  # ~600 API calls, ~18s, good confidence

# Fast
OSRM_CHUNK_SIZE = 25  # ~250 API calls, ~9s, fair confidence
```

### Densification Intervals

```bash
--densify-points 50   # Very smooth (large files)
--densify-points 100  # Balanced (recommended)
--densify-points 200  # Lightweight
# (omit for no densification)
```

---

## Expected Performance

| Routes | Snapping | Densify | OSRM | Time | Size |
|--------|----------|---------|------|------|------|
| 21 | No | No | - | 1s | 840KB |
| 21 | No | Yes | - | 2s | 1.0MB |
| 21 | Yes | Yes | Local | 18s | 1.4MB |
| 21 | Yes | Yes | Public | 5min | 1.4MB |

---

## Common Issues

### "No routes found"
```bash
# Check route IDs
head routes.txt

# Use route_id (not route_short_name)
gtfs2kml . ./output -r J10CWL  # ✓ Correct
gtfs2kml . ./output -r J10      # ✗ Wrong
```

### OSRM connection failed
```bash
docker ps | grep osrm-backend  # Check running
docker restart osrm-backend    # Restart if needed
curl http://localhost:5000/route/v1/driving/103.76,1.46;103.77,1.47
```

### Low confidence warnings
```bash
# Normal - falls back to original GTFS
# To reduce warnings:
# 1. Use smaller chunk size (6-10)
# 2. Update OSM data
# 3. Try different provider
```

---

## Output Verification

```bash
# Count files
ls output/*.kml | wc -l

# Check sizes
du -sh output/
ls -lh output/*.kml | sort -k5 -hr | head -10

# Check logs
grep -i error output.log
grep -i warning output.log | grep -v confidence
```

---

## API Providers

### Mapbox (100K free/month)
```bash
# Get key: https://account.mapbox.com/
export MAPBOX_API_KEY="your_key"

gtfs2kml ./gtfs_data ./output \
  --snap-to-roads \
  --snap-provider mapbox \
  --snap-api-key $MAPBOX_API_KEY \
  --densify-points 100 \
  --snap-cache-dir ./snap_cache
```

### Google Roads (Paid)
```bash
gtfs2kml ./gtfs_data ./output \
  --snap-to-roads \
  --snap-provider google \
  --snap-api-key $GOOGLE_API_KEY \
  --densify-points 100 \
  --snap-cache-dir ./snap_cache
```

---

## Automation Script

```bash
#!/bin/bash
# update_transit_maps.sh

set -e

# Pull latest GTFS
wget https://transit-agency.com/gtfs.zip -O gtfs.zip
unzip -o gtfs.zip -d ./gtfs_data

# Generate KML
gtfs2kml ./gtfs_data ./public/maps \
  --snap-to-roads \
  --snap-provider osrm \
  --densify-points 100 \
  --snap-cache-dir ./snap_cache

# Deploy
aws s3 sync ./public/maps s3://my-bucket/transit-maps/ \
  --delete \
  --cache-control "max-age=3600"
```

---

## File Size Guidelines

| Route | Original | +Dense | +Snap | +Both |
|-------|----------|--------|-------|-------|
| Short (5km) | 10-20KB | 15-30KB | 15-35KB | 20-40KB |
| Medium (15km) | 30-50KB | 50-80KB | 50-90KB | 70-120KB |
| Long (30km) | 50-80KB | 80-130KB | 80-150KB | 120-180KB |

**MyBAS Johor: 840KB → 1.4MB (21 routes)**

---

## Support

- **Docs**: `README.md`, `ROAD_SNAPPING_GUIDE.md`, `OSRM_LOCAL_SETUP.md`
- **GTFS Spec**: https://gtfs.org/
- **Issues**: Report bugs on GitHub
