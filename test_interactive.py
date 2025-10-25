#!/usr/bin/env python3
"""
Interactive DeezChat Docker Test
"""

import subprocess
import time
import os

def interactive_docker_test():
    """Test DeezChat with actual commands"""
    
    print("🎮 DEEZCHAT INTERACTIVE DOCKER TEST")
    print("=" * 50)
    
    # Start container in background with commands piped
    commands = [
        "/help",           # Show help
        "/join general",    # Join channel
        "Hello BitChat!",   # Send message
        "/quit"            # Exit
    ]
    
    input_text = "\n".join(commands) + "\n"
    
    print("🚀 Starting container with test commands...")
    print(f"📝 Commands to execute: {commands}")
    
    # Run container with commands piped
    result = subprocess.run([
        "docker", "run", "--rm", "-i",
        "--name", "deezchat-interactive",
        "-v", f"{os.getcwd()}/data:/app/data",
        "-v", f"{os.getcwd()}/config:/app/config", 
        "-v", f"{os.getcwd()}/logs:/app/logs",
        "deezchat:optimized", "--debug"
    ], input=input_text, text=True, capture_output=True, timeout=10)
    
    print("📋 Container Output:")
    print("-" * 40)
    
    output = result.stdout
    errors = result.stderr
    
    # Process output line by line
    lines = output.split('\n')
    for line in lines:
        if line.strip():
            print(f"📤 {line}")
    
    if errors:
        print("⚠️  Errors:")
        print(errors)
    
    # Analyze results
    print("\n" + "=" * 50)
    print("📊 TEST ANALYSIS")
    print("=" * 50)
    
    success_indicators = {
        "Welcome to DeezChat": "✅ Application startup",
        "fingerprint:": "✅ Crypto identity generated",
        "Available commands": "✅ Help command working",
        "Joined channel: general": "✅ Channel join working",
        "[general] you: Hello BitChat!": "✅ Message sending working",
        "Goodbye!": "✅ Clean exit"
    }
    
    for indicator, message in success_indicators.items():
        if indicator in output:
            print(f"{message}")
        else:
            print(f"❌ Missing: {indicator}")
    
    # Check for BitChat features
    bitches_features = {
        "Noise": "✅ Noise Protocol encryption",
        "BLE": "✅ Bluetooth LE ready",
        "mesh": "✅ Mesh networking"
    }
    
    for feature, message in bitches_features.items():
        if feature.lower() in output.lower():
            print(f"{message}")
    
    print(f"\n🏁 Return code: {result.returncode}")
    print("🎉 INTERACTIVE TEST COMPLETED")

if __name__ == "__main__":
    interactive_docker_test()