import json
import sys
import os

# Ensure the parent directory is in the path so we can import core.data_reader
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.data_reader import RealDataReader

def main():
    try:
        status = RealDataReader.get_real_system_status()
        print(json.dumps(status, indent=2))
    except Exception as e:
        print(f"Error test: {str(e)}")

if __name__ == "__main__":
    main()
