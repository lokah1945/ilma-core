"""CLI for streaming test."""
import argparse
from .streamer import ILMAStreamer

def main():
    parser = argparse.ArgumentParser(description="Test streaming")
    parser.add_argument("--message", default="Test message")
    parser.add_argument("--label", default="thinking")
    
    args = parser.parse_args()
    
    streamer = ILMAStreamer()
    streamer.stream(args.label, args.message)
    streamer.done("Done!")

if __name__ == "__main__":
    main()
