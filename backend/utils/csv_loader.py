"""
CSV Loader Utility for Instagram Bot
Loads targets (hashtags or usernames) from CSV files.

CSV Formats Supported:

1. Single column (hashtag OR username):
    hashtag          OR      username
    #travel                  johndoe
    #food                    janedoe
    photography              someuser

2. Two columns (both hashtag AND username in one file):
    hashtag,username
    #travel,johndoe
    #food,janedoe
    ,someuser           (empty hashtag, only username)
    #art,               (only hashtag, empty username)
"""

import csv
import os


def load_targets_from_csv(csv_path, log=print):
    """
    Load targets from a CSV file.
    
    Supports:
    - Single column: header is 'hashtag' or 'username'
    - Two columns: headers are 'hashtag,username' (mixed targets)
    
    Args:
        csv_path: Path to the CSV file
        log: Logging function (default: print)
    
    Returns:
        dict: {
            'type': 'hashtag', 'username', or 'mixed',
            'targets': list of targets (with # for hashtags),
            'count': number of targets
        }
        Returns None if loading fails.
    """
    if not csv_path or not os.path.exists(csv_path):
        log(f"❌ CSV file not found: {csv_path}")
        return None
    
    try:
        targets = []
        target_type = None
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            # Try to detect delimiter
            sample = file.read(1024)
            file.seek(0)
            
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            except:
                dialect = csv.excel  # Default to comma
            
            reader = csv.reader(file, dialect)
            
            # Read header row
            header = next(reader, None)
            if not header:
                log("❌ CSV file is empty")
                return None
            
            # Normalize headers
            headers = [h.strip().lower() for h in header]
            
            # Check for two-column format (hashtag AND username)
            hashtag_col = None
            username_col = None
            
            for i, h in enumerate(headers):
                if h in ['hashtag', 'hashtags', '#', 'tag', 'tags']:
                    hashtag_col = i
                elif h in ['username', 'usernames', 'user', 'users', 'profile', 'profiles']:
                    username_col = i
            
            # Determine format type
            if hashtag_col is not None and username_col is not None:
                # Two-column mixed format
                target_type = 'mixed'
                log(f"📋 Detected mixed format (hashtag + username columns)")
                
                for row in reader:
                    # Get hashtag value if exists
                    if hashtag_col < len(row):
                        hashtag = row[hashtag_col].strip()
                        if hashtag:
                            if not hashtag.startswith('#'):
                                hashtag = '#' + hashtag
                            targets.append(hashtag)
                    
                    # Get username value if exists
                    if username_col < len(row):
                        username = row[username_col].strip()
                        if username:
                            if username.startswith('@'):
                                username = username[1:]
                            targets.append(username)
                            
            elif hashtag_col is not None:
                # Single column: hashtag only
                target_type = 'hashtag'
                for row in reader:
                    if hashtag_col < len(row) and row[hashtag_col].strip():
                        target = row[hashtag_col].strip()
                        if not target.startswith('#'):
                            target = '#' + target
                        targets.append(target)
                        
            elif username_col is not None:
                # Single column: username only
                target_type = 'username'
                for row in reader:
                    if username_col < len(row) and row[username_col].strip():
                        target = row[username_col].strip()
                        if target.startswith('@'):
                            target = target[1:]
                        targets.append(target)
            else:
                # Unknown header, try first column as username
                log(f"⚠️ Unknown header '{header[0]}'. Expected 'hashtag' or 'username'")
                log("📝 Treating as username by default...")
                target_type = 'username'
                
                for row in reader:
                    if row and row[0].strip():
                        target = row[0].strip()
                        if target.startswith('@'):
                            target = target[1:]
                        targets.append(target)
        
        if not targets:
            log("❌ No targets found in CSV file")
            return None
        
        log(f"✅ Loaded {len(targets)} targets ({target_type}) from CSV")
        return {
            'type': target_type,
            'targets': targets,
            'count': len(targets)
        }
        
    except Exception as e:
        log(f"❌ Error reading CSV: {e}")
        return None


def validate_csv_format(csv_path):
    """
    Validate if a CSV file has the correct format.
    
    Args:
        csv_path: Path to the CSV file
    
    Returns:
        tuple: (is_valid: bool, message: str, target_type: str or None)
    """
    if not csv_path or not os.path.exists(csv_path):
        return False, f"File not found: {csv_path}", None
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            # Try to detect delimiter
            sample = file.read(1024)
            file.seek(0)
            
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            except:
                dialect = csv.excel
            
            reader = csv.reader(file, dialect)
            header = next(reader, None)
            
            if not header:
                return False, "CSV file is empty", None
            
            # Normalize headers
            headers = [h.strip().lower() for h in header]
            
            has_hashtag = any(h in ['hashtag', 'hashtags', '#', 'tag', 'tags'] for h in headers)
            has_username = any(h in ['username', 'usernames', 'user', 'users', 'profile', 'profiles'] for h in headers)
            
            if has_hashtag and has_username:
                return True, "Valid mixed CSV (hashtag + username)", 'mixed'
            elif has_hashtag:
                return True, "Valid hashtag CSV", 'hashtag'
            elif has_username:
                return True, "Valid username CSV", 'username'
            else:
                return False, f"Invalid header: '{', '.join(header)}'. Use 'hashtag' and/or 'username'", None
                
    except Exception as e:
        return False, f"Error reading file: {e}", None


def create_sample_csv(output_path, target_type='hashtag', samples=None):
    """
    Create a sample CSV file.
    
    Args:
        output_path: Path to save the CSV file
        target_type: 'hashtag' or 'username'
        samples: List of sample targets (optional)
    """
    if samples is None:
        if target_type == 'hashtag':
            samples = ['#travel', '#food', '#photography', '#nature', '#art']
        else:
            samples = ['instagram', 'nature', 'travel', 'food', 'art']
    
    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([target_type])
            for sample in samples:
                writer.writerow([sample])
        return True
    except Exception as e:
        print(f"Error creating sample CSV: {e}")
        return False
