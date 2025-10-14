import os
import json

def test_file_structure():
    required_files = [
        'package.json',
        'vite.config.js',
        'tailwind.config.js',
        'src/main.jsx',
        'src/App.jsx',
        'src/index.css',
        'server/main.py',
        'requirements.txt'
    ]
    
    for file_path in required_files:
        assert os.path.exists(file_path), f"Required file missing: {file_path}"
        print(f"✓ Found: {file_path}")

def test_package_json():
    with open('package.json', 'r') as f:
        package_data = json.load(f)
    
    required_deps = ['react', 'react-dom', 'vite', 'tailwindcss', 'dexie', '@dnd-kit/core']
    for dep in required_deps:
        assert dep in package_data['dependencies'], f"Missing dependency: {dep}"
        print(f"✓ Dependency found: {dep}")

def test_react_components():
    component_files = [
        'src/components/PositionFilter.jsx',
        'src/components/PlayerRankings.jsx',
        'src/components/SleeperAlerts.jsx'
    ]
    
    for component_file in component_files:
        assert os.path.exists(component_file), f"Component missing: {component_file}"
        with open(component_file, 'r') as f:
            content = f.read()
            assert 'export default' in content, f"Component not properly exported: {component_file}"
        print(f"✓ Component validated: {component_file}")

def test_python_backend():
    assert os.path.exists('server/main.py'), "Python backend missing"
    
    with open('server/main.py', 'r') as f:
        content = f.read()
        assert 'FastAPI' in content, "FastAPI not imported"
        assert '@app.get("/api/scrape-fantasy-data")' in content, "API endpoint not found"
        assert 'scrape-fantasy-data' in content, "Scraping functionality missing"
    
    print("✓ Python backend validated")

def test_data_structure():
    with open('server/main.py', 'r') as f:
        content = f.read()
    
    required_fields = ['player_name', 'team', 'position', 'power_score', 'sleeper_rating']
    for field in required_fields:
        assert field in content, f"Required field missing in data: {field}"
        print(f"✓ Data field found: {field}")

if __name__ == "__main__":
    print("Running validation tests...")
    test_file_structure()
    test_package_json()
    test_react_components()
    test_python_backend()
    test_data_structure()
    print("\n✅ All validation tests passed!")