import os
import sys

sys.path.insert(0, ".")

from core.wordpress_publisher import WordPressPublisher
import re

def fix_links(post_id):
    wp = WordPressPublisher()
    print(f"Fetching post {post_id}...")
    
    res = wp._api_request("GET", f"posts/{post_id}?context=edit")
    if not res.get("success"):
        print("Error fetching post:", res)
        return
        
    post_data = res.get("data", {})
    content = post_data.get("content", {}).get("raw", "")
    
    if not content:
        print("No content found.")
        return

    # Links replacements
    link1 = '<p><a href="https://falconherbs.com/product-category/immunity/">Explore our Ayurvedic adaptogens</a></p>'
    link2 = '<p><a href="https://falconherbs.com/product/ashwagandha-root-whole-100g/">Shop Falcon Herbs Ashwagandha</a></p>'
    link3 = '<p><a href="https://falconherbs.com/blog/">Read more Ayurvedic wellness guides</a></p>'
    
    modified_content = content
    
    # We use regex to match the lines based on the text contents
    modified_content = re.sub(
        r'<p>.*?Explore our full line of Ayurvedic adaptogens</p>', link1, modified_content
    )
    modified_content = re.sub(
        r'<p>.*?Learn how to make a calming ashwagandha latte</p>', link2, modified_content
    )
    modified_content = re.sub(
        r'<p>.*?Understand your dosha with our free guide</p>', link3, modified_content
    )

    print(f"Original length: {len(content)}")
    print(f"Fixed length: {len(modified_content)}")

    if content == modified_content:
        print("No changes were made. The links might have already been fixed or not found.")
        return

    payload = {
        "content": modified_content
    }
    print("Updating post via WP API...")
    update_res = wp._api_request("POST", f"posts/{post_id}", data=payload)
    
    if not update_res.get("success"):
        print("Failed to update post:", update_res)
    else:
        print("Post updated successfully!")

if __name__ == "__main__":
    fix_links(8252)
