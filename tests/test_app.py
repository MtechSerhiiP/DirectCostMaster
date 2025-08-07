"""
Simple test script to check if our application imports correctly
"""
try:
    from main import DirectCostMasterApp
    from dc_processor import DirectCostProcessor, DCMasterFileManager
    
    print("✅ All imports successful!")
    
    # Test the month extraction
    processor = DirectCostProcessor()
    
    test_filenames = [
        "Project_ABC_June_2025.xlsx",
        "P&L_ProjectXYZ_July2025.xlsx", 
        "March_Project_Results.xlsx",
        "project_data_apr_2025.xlsx"
    ]
    
    print("\n📅 Testing month extraction:")
    for filename in test_filenames:
        month = processor.extract_month_from_filename(filename)
        project = processor.extract_project_name_from_filename(filename)
        print(f"  {filename} -> Month: {month}, Project: {project}")
    
    print("\n🚀 Application is ready to run!")
    print("To start the app, run: python main.py")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
