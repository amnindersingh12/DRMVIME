#!/usr/bin/env python3
"""
TwinVine Server - Simplified entry point using modular architecture
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from twinvine import TwinVineServer
except ImportError:
    # Fallback to legacy mode if modular import fails
    print("⚠️  Using legacy server mode...")
    exec(open(Path(__file__).parent / 'twinvine_server_legacy.py').read())
    sys.exit(0)

def main():
    """Main entry point for TwinVine server."""
    server = TwinVineServer(
        host='localhost',
        port=8765,
        queue_path='./vaults/course_cache/auto_queue.json'
    )
    
    try:
        server.run(debug=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())