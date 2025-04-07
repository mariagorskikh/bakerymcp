#!/usr/bin/env python3
import subprocess
import sys

def run_pip_freeze():
    """Run pip freeze to see installed packages"""
    print("Currently installed packages:")
    subprocess.run(["pip", "freeze"], check=False)

def check_dependency_info(package):
    """Get detailed info about a package's dependencies"""
    print(f"\nChecking dependencies for {package}:")
    subprocess.run(["pip", "show", package], check=False)

def analyze_dependency_tree():
    """Analyze the dependency tree for our key packages"""
    try:
        print("\nAttempting to analyze dependency tree (this may fail if pipdeptree isn't installed):")
        subprocess.run(["pip", "install", "pipdeptree"], check=True)
        subprocess.run(["pipdeptree", "-p", "fast-agent-mcp", "-p", "fastapi", "-p", "uvicorn"], check=False)
    except Exception as e:
        print(f"Error analyzing dependency tree: {e}")

def check_fast_agent_version():
    """Check fast-agent-mcp version compatibility"""
    try:
        print("\nChecking fast-agent-mcp compatibility:")
        subprocess.run(["pip", "install", "fast-agent-mcp==0.2.4", "--no-deps", "--dry-run"], check=False)
        
        # Try to install MCP with specific versions
        print("\nTrying different MCP versions:")
        for version in ["1.1.3", "1.2.0", "1.3.0", "1.5.0", "1.6.0"]:
            print(f"\nTrying MCP version {version}:")
            result = subprocess.run(
                ["pip", "install", f"mcp=={version}", "--dry-run"], 
                capture_output=True, 
                text=True,
                check=False
            )
            if result.returncode == 0:
                print(f"MCP {version} seems compatible!")
            else:
                print(f"MCP {version} has conflicts: {result.stderr.strip()}")
    except Exception as e:
        print(f"Error checking fast-agent compatibility: {e}")

if __name__ == "__main__":
    print("Dependency Conflict Analyzer")
    print("===========================\n")
    
    run_pip_freeze()
    
    # Check these key packages
    packages_to_check = ["fast-agent-mcp", "fastapi", "uvicorn", "mcp"]
    for package in packages_to_check:
        check_dependency_info(package)
    
    analyze_dependency_tree()
    check_fast_agent_version()
    
    print("\nAnalysis complete. Based on the output above, you can determine which package versions are conflicting.") 