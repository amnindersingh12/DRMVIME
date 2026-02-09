#!/usr/bin/env python3
"""Remove duplicates from queue and fix numbering"""
import json
from pathlib import Path

queue_file = Path("vaults/course_cache/auto_queue.json")
data = json.load(open(queue_file))

# Remove duplicates based on MPD URL
seen = set()
unique = []
for item in data:
    if item['mpd_url'] not in seen:
        seen.add(item['mpd_url'])
        unique.append(item)

# Renumber
for i, item in enumerate(unique):
    item['number'] = i + 1
    title = item['metadata'].get('title', f'lesson{i+1:02d}')[:20]
    item['filename'] = f"lesson{i+1:02d}_{title}"

# Save
json.dump(unique, open(queue_file, 'w'), indent=2)

print(f"✅ Removed {len(data) - len(unique)} duplicates")
print(f"📋 Now {len(unique)} unique lessons in queue")
