"""
Test script to debug row indexing issues
"""
import pandas as pd
from dc_processor import DirectCostProcessor

def test_month_section_finding():
    """Test the month section finding logic"""
    print("🔍 Testing Month Section Finding...")
    
    # Create a mock DataFrame that simulates the Excel structure
    mock_data = {
        'Col1': [
            'DL costs breakdown (direct) // USD',
            '',
            '',
            'February 2025',
            'Employee/Ticket',
            'John Doe',
            'Jane Smith', 
            'PM role charge',
            'TOTAL',
            '',
            'March 2025',
            'Employee/Ticket',
            'Bob Wilson',
            'Alice Brown',
            'TOTAL'
        ],
        'Col2': [None] * 15,
        'Col3': [None] * 15
    }
    
    df = pd.DataFrame(mock_data)
    print("\n📊 Mock DataFrame:")
    print(df.head(15))
    
    processor = DirectCostProcessor()
    
    # Test finding February
    start, end = processor._find_month_section(df, 'February')
    print(f"\n🔍 February section: start={start}, end={end}")
    
    if start is not None and end is not None:
        section_data = df.iloc[start:end]
        print(f"February data rows:")
        for i, row in section_data.iterrows():
            print(f"  Row {i}: {row.iloc[0]}")
    
    # Test finding March
    start, end = processor._find_month_section(df, 'March')
    print(f"\n🔍 March section: start={start}, end={end}")
    
    if start is not None:
        section_data = df.iloc[start:end] if end else df.iloc[start:]
        print(f"March data rows:")
        for i, row in section_data.iterrows():
            print(f"  Row {i}: {row.iloc[0]}")

if __name__ == "__main__":
    test_month_section_finding()
    print("\n✅ Test completed!")
