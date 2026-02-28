import sys
sys.path.insert(0, ".")

from agents.content_producer import ContentProducer
import traceback

def test_blog_draft():
    try:
        cp = ContentProducer()
        res = cp.draft_blog_post(
            topic="Ashwagandha benefits for stress", 
            keyword="ashwagandha for stress"
        )
        print("====== RESULT ======")
        import json
        try:
            print(json.dumps(res, indent=2))
        except:
            print(res)
    except Exception as e:
        print("Error:", e)
        traceback.print_exc()

if __name__ == "__main__":
    test_blog_draft()
