import re
import pandas as pd

def normalize_address(address_string):
    """
    Standardizes messy street addresses to a common format for accurate deduplication.
    Converts to uppercase, strips punctuation, and standardizes common abbreviations.
    """
    if not isinstance(address_string, str):
        return ""
    
    addr = address_string.upper().strip()
    # Remove periods and commas
    addr = re.sub(r'[.,]', '', addr)
    # Standardize abbreviations
    replacements = {
        r'\bSTREET\b': 'ST',
        r'\bAVENUE\b': 'AVE',
        r'\bDRIVE\b': 'DR',
        r'\bROAD\b': 'RD',
        r'\bBOULEVARD\b': 'BLVD',
        r'\bLANE\b': 'LN',
        r'\bCOURT\b': 'CT',
        r'\bHIGHWAY\b': 'HWY'
    }
    for pattern, replacement in replacements.items():
        addr = re.sub(pattern, replacement, addr)
        
    # Remove excessive whitespace
    return re.sub(r'\s+', ' ', addr)

def clean_phone_number(phone_string):
    """
    Strips formatting from phone numbers, returning only digits.
    Returns None if the length is not standard US (10 digits).
    """
    if not isinstance(phone_string, str):
        return None
        
    digits = re.sub(r'\D', '', phone_string)
    
    # Strip leading 1 if US country code
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
        
    if len(digits) == 10:
        return digits
    return None

def deduplicate_dataframe(df, target_column="Property_Address"):
    """
    Normalizes a target column and removes duplicates, prioritizing rows with more populated data.
    """
    if target_column not in df.columns:
        return df
        
    # Create a normalized temporary column
    df['_normalized'] = df[target_column].apply(normalize_address)
    
    # Sort by number of non-null values to keep the most complete record when dropping duplicates
    df['_non_null_count'] = df.notnull().sum(axis=1)
    df = df.sort_values('_non_null_count', ascending=False)
    
    df_clean = df.drop_duplicates(subset=['_normalized'], keep='first')
    
    # Cleanup temp columns
    df_clean = df_clean.drop(columns=['_normalized', '_non_null_count'])
    return df_clean

if __name__ == "__main__":
    # Test suite
    print(normalize_address(" 123   Main Street,  Apt 4B. "))  # "123 MAIN ST APT 4B"
    print(clean_phone_number("(555) 123-4567 "))               # "5551234567"
