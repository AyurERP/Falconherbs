import os
import sys

sys.path.insert(0, ".")

from core.wordpress_publisher import WordPressPublisher
import re

def fix_post(post_id):
    wp = WordPressPublisher()
    print(f"Fetching post {post_id}...")
    
    # 1. Fetch Post with context=edit to get raw content
    res = wp._api_request("GET", f"posts/{post_id}?context=edit")
    if not res.get("success"):
        print("Error fetching post:", res)
        return
        
    post_data = res.get("data", {})

    content = post_data.get("content", {}).get("raw", "")
    title = post_data.get("title", {}).get("raw", "")
    excerpt = post_data.get("excerpt", {}).get("raw", "")

    print(f"Original content length: {len(content)}")

    # 2. Fix issues
    fixes = [
        (r"supports naturalthcare", "healthcare"),
        (r"supports naturalthy", "healthy"),
        (r"supports naturalth", "health"), 
        (r"Supports naturalthcare", "Healthcare"),
        (r"Supports naturalthy", "Healthy"),
        (r"Supports naturalth", "Health")
    ]
    
    for bad, good in fixes:
        content = re.sub(bad, good, content)
        title = re.sub(bad, good, title)
        excerpt = re.sub(bad, good, excerpt)

    print(f"Fixed content length: {len(content)}")

    # 3. Update via WP API
    payload = {
        "content": content,
        "title": title,
        "excerpt": excerpt
    }
    print("Updating post via WP API...")
    update_res = wp._api_request("POST", f"posts/{post_id}", data=payload)
    
    if not update_res.get("success"):
        print("Failed to update post:", update_res)
    else:
        print("Post updated successfully!")

if __name__ == "__main__":
    fix_post(8252)
