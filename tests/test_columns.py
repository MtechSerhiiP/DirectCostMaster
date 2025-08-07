"""
Test script for column mapping and Excel processing
"""
import pandas as pd
from dc_processor import DirectCostProcessor

def test_column_mapping():
    """Test the column mapping functionality with Unnamed columns"""
    print("🧪 Testing Column Mapping with Unnamed columns...")
    
    # Simulate what pandas creates when reading Excel with merged/unnamed columns
    test_columns = [
        'Employee/Ticket',
        'TOTAL Hours direct',
        'Unnamed: 2',
        'Unnamed: 3', 
        'Unnamed: 4',
        'TOTAL DL costs',
        'Unnamed: 6',
        'Unnamed: 7',
        'Unnamed: 8',
        'Unnamed: 9',
        'Unnamed: 10',
        'Unnamed: 11',
        'Unnamed: 12',
        'VC.Medical Insurance'
    ]
    
    processor = DirectCostProcessor()
    mapping = processor._create_column_mapping(test_columns)
    
    print("\n📋 Column Mapping Results:")
    for original, mapped in mapping.items():
        print(f"  {original} -> {mapped}")
    
    # Test position-based mapping
    print("\n🎯 Position-based Standard Names:")
    for pos in range(1, 14):
        standard_name = processor._get_standard_name_for_position(pos)
        if standard_name:
            print(f"  Position {pos}: {standard_name}")

def test_filename_extraction():
    """Test project name and month extraction from filenames"""
    print("\n📂 Testing Filename Extraction...")
    
    test_files = [
        "Strategic.UHG.NICE.TAM - June 2025.XLSX",
        "Project ABC - March 2025.xlsx",
        "Company XYZ - July 2025.xls",
        "P&L Report - September 2025.XLSX"
    ]
    
    processor = DirectCostProcessor()
    
    for filename in test_files:
        project = processor.extract_project_name_from_filename(filename)
        month = processor.extract_month_from_filename(filename)
        print(f"  {filename}")
        print(f"    Project: {project}")
        print(f"    Month: {month}")
        print()

if __name__ == "__main__":
    test_column_mapping()
    test_filename_extraction()
    print("✅ All tests completed!")
