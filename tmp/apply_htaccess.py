import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from dotenv import load_dotenv
load_dotenv()
from core.cpanel_connector import cpanel

def update_htaccess():
    # 1. Read the CSV
    try:
        df = pd.read_csv('tmp/rank_math_redirects_correct.csv')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 2. Generate redirect strings
    redirects = []
    redirects.append("\n# BEGIN AUTO-GENERATED SEO 301 REDIRECTS (FALCON AGENCY)")
    for _, row in df.iterrows():
        source = row['source']
        target = row['destination']
        if source and target:
            redirects.append(f"Redirect 301 {source} {target}")
    redirects.append("# END AUTO-GENERATED SEO 301 REDIRECTS\n")

    redirect_block = "\n".join(redirects)
    print("Generated Redirect Block:")
    print(redirect_block)

    # 3. Connect to cPanel and get current .htaccess
    print("\nFetching current .htaccess from cPanel...")
    # Checking if the cpanel is configured correctly via environment variables.
    
    current_content = cpanel.get_file_content("public_html", ".htaccess")
    if current_content is None:
        print("❌ Error: Could not fetch .htaccess from cPanel. Check credentials.")
        return

    print("Current .htaccess size:", len(current_content), "bytes")

    # 4. Check if we already added it to avoid duplicates
    if "# BEGIN AUTO-GENERATED SEO 301 REDIRECTS (FALCON AGENCY)" in current_content:
        print("⚠️ Redirects block already exists in .htaccess. Aborting to avoid duplicates.")
        return

    # 5. Append new content
    new_content = current_content + redirect_block

    # 6. Save back to cPanel
    print("\nSaving updated .htaccess to cPanel...")
    success = cpanel.save_file_content("public_html", ".htaccess", new_content)
    
    if success:
        print("✅ Successfully updated .htaccess via cPanel UAPI!")
    else:
        print("❌ Failed to save .htaccess.")
    
    # 7. Verify
    verify_content = cpanel.get_file_content("public_html", ".htaccess")
    if verify_content and "# BEGIN AUTO-GENERATED SEO 301 REDIRECTS" in verify_content:
        print("✅ Verification passed: Redirects are present in the remote file.")
    else:
        print("❌ Verification failed: Redirects are not present in the remote file.")

if __name__ == "__main__":
    update_htaccess()
