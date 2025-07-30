# Direct Cost Master Application

A modern web-based application for processing P&L Excel files and consolidating Direct Cost data using NiceGUI.

## Features

- **Modern Web Interface**: Clean, minimalist design with responsive layout
- **In-Memory File Processing**: Uses IOBytes approach - no temporary files on disk
- **Excel File Support**: Handles .xlsx and .xls files with multiple sheets
- **Automated Data Processing**: Implements business rules for DL and VC costs
- **Master File Generation**: Consolidates data from multiple projects
- **Real-time Preview**: View data before processing
- **Download Results**: Export consolidated data as Excel file

## Installation

1. Install required packages:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python main.py
```

3. Open your browser and navigate to `http://127.0.0.1:8080`

## How to Use

1. **Upload P&L File**: Drag and drop or click to upload your Excel P&L file
2. **Preview Data**: Select and preview different sheets from your file
3. **Process Data**: Click "Process P&L File" to extract and classify Direct Costs
4. **Download Results**: Use "Download Master DC File" to get the consolidated data

## Business Logic

The application processes two types of data according to the requirements:

### DL Costs (Direct) Processing
- Extracts employee data and hours
- Classifies records into buckets:
  - **PM role charge**: For PM role charge entries
  - **Sick leave**: When sick leave hours match total direct hours
  - **Bonus**: When unconditional bonus matches total DL amount
  - **Regular DL**: For standard employee records

### VC Costs (Direct) Processing
- Extracts variable cost data
- Classifies records into buckets:
  - **Recruiting costs**: For items starting with "Recruiting costs"
  - **DC-other DC**: For all other variable costs

## File Structure

```
DirectCostMaster/
├── main.py                 # Main application with NiceGUI interface
├── dc_processor.py         # Business logic for data processing
├── requirements.txt        # Python dependencies
├── process_description.txt # Original business requirements
└── README.md              # This file
```

## Technical Details

- **Framework**: NiceGUI for web interface
- **Data Processing**: pandas for Excel manipulation
- **Excel Support**: openpyxl engine for .xlsx files
- **Memory Management**: IOBytes approach for file handling
- **Logging**: Comprehensive logging for debugging

## Browser Compatibility

The application works with all modern browsers including Chrome, Firefox, Safari, and Edge.

## Error Handling

The application includes comprehensive error handling and user feedback:
- File format validation
- Missing sheet detection
- Data validation warnings
- Processing error notifications

## Development

To extend the application:
1. Modify `dc_processor.py` for new business rules
2. Update `main.py` for UI changes
3. Test with sample P&L files

## Support

For issues or questions, check the application logs or review the process description file for business requirements.
