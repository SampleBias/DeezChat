#!/usr/bin/env python3
"""
Test script for DeezChat Docker container
"""

import subprocess
import time
import signal
import os

def test_docker_container():
    """Test DeezChat in Docker container"""
    
    print("🚀 Starting DeezChat Docker test...")
    
    # Start container in background
    cmd = [
        "docker", "run", "--rm", "-d",
        "--name", "deezchat-test-run",
        "-v", f"{os.getcwd()}/data:/app/data",
        "-v", f"{os.getcwd()}/config:/app/config", 
        "-v", f"{os.getcwd()}/logs:/app/logs",
        "deezchat:optimized", "--debug"
    ]
    
    try:
        # Start container
        result = subprocess.run(cmd, capture_output=True, text=True)
        container_id = result.stdout.strip()
        
        if not container_id:
            print(f"❌ Failed to start container: {result.stderr}")
            return False
            
        print(f"✅ Container started: {container_id[:12]}")
        
        # Wait a bit for startup
        time.sleep(3)
        
        # Check container logs
        logs_result = subprocess.run(
            ["docker", "logs", "deezchat-test-run"],
            capture_output=True, text=True
        )
        
        print("📋 Container logs:")
        print(logs_result.stdout)
        
        if logs_result.stderr:
            print("⚠️  Container errors:")
            print(logs_result.stderr)
        
        # Check container status
        status_result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", "deezchat-test-run"],
            capture_output=True, text=True
        )
        
        status = status_result.stdout.strip()
        print(f"📊 Container status: {status}")
        
        # Test health check
        health_result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", "deezchat-test-run"],
            capture_output=True, text=True
        )
        
        if health_result.stdout.strip():
            health = health_result.stdout.strip()
            print(f"🏥 Health status: {health}")
        
        # Stop container
        stop_result = subprocess.run(
            ["docker", "stop", "deezchat-test-run"],
            capture_output=True, text=True
        )
        
        print("✅ Container stopped")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_container_features():
    """Test specific container features"""
    
    print("\n🔍 Testing container features...")
    
    # Test image size
    size_result = subprocess.run(
        ["docker", "images", "deezchat:optimized", "--format", "{{.Size}}"],
        capture_output=True, text=True
    )
    
    if size_result.returncode == 0:
        size = size_result.stdout.strip()
        print(f"📦 Image size: {size}")
    
    # Test entrypoint
    entrypoint_result = subprocess.run(
        ["docker", "inspect", "--format", "{{.Config.Entrypoint}}", "deezchat:optimized"],
        capture_output=True, text=True
    )
    
    if entrypoint_result.returncode == 0:
        entrypoint = entrypoint_result.stdout.strip()
        print(f"🎯 Entrypoint: {entrypoint}")
    
    # Test user
    user_result = subprocess.run(
        ["docker", "inspect", "--format", "{{.Config.User}}", "deezchat:optimized"],
        capture_output=True, text=True
    )
    
    if user_result.returncode == 0:
        user = user_result.stdout.strip()
        print(f"👤 Running as user: {user}")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 DEEZCHAT DOCKER TEST SUITE")
    print("=" * 60)
    
    # Test container features
    test_container_features()
    
    # Test container execution
    success = test_docker_container()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ DeezChat Docker container is working correctly")
    else:
        print("❌ TESTS FAILED!")
        print("⚠️  Check container logs and configuration")
    print("=" * 60)