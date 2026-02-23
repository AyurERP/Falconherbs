# tests/test_pr_outreach.py

import sys
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.pr_outreach import PROutreach

def mock_llm(prompt, model):
    """Simple mock LLM response"""
    return "Subject: Collaboration with Falcon Herbs\n\nHi Creator, loved your video about digestion. Let's work together!"

class TestPROutreach:
    def setup_method(self):
        # Mock config to avoid missing file errors
        self.mock_config = {
            "outreach": {
                "youtube_api_key": "MOCK_KEY",
                "min_subscribers": 5000,
                "max_results": 5,
                "product_focus": "Ayurvedic wellness"
            }
        }
        
        with patch('agents.pr_outreach.PROutreach._load_config', return_value=self.mock_config):
            with patch('agents.pr_outreach.build'):
                self.outreach = PROutreach(llm_caller=mock_llm)

    @patch('agents.pr_outreach.PROutreach._load_config')
    def test_find_influencers_mock(self, mock_load):
        mock_load.return_value = self.mock_config
        
        # Setup mock YouTube client responses
        mock_youtube = MagicMock()
        self.outreach.youtube = mock_youtube
        
        # 1. Search response (channels)
        mock_youtube.search().list().execute.side_effect = [
            {
                "items": [
                    {"id": {"channelId": "UC123"}, "snippet": {"title": "Ayurveda Guru"}},
                    {"id": {"channelId": "UC456"}, "snippet": {"title": "Patanjali Ayurved"}},
                    {"id": {"channelId": "UC789"}, "snippet": {"title": "Himalaya Wellness"}},
                    {"id": {"channelId": "UC000"}, "snippet": {"title": "Dr. Priya Sharma Ayurveda"}},
                    {"id": {"channelId": "UC111"}, "snippet": {"title": "The Ayurveda Company"}},
                    {"id": {"channelId": "UC222"}, "snippet": {"title": "Ayurveda With Nidhi"}},
                ]
            },
            { "items": [{"snippet": {"title": "Digestion tips"}}] }, # Guru
            { "items": [{"snippet": {"title": "Priya video"}}] },    # Dr. Priya
            { "items": [{"snippet": {"title": "Company video"}}] },  # T.A.C
            { "items": [{"snippet": {"title": "Nidhi video"}}] },    # Nidhi
        ]
        
        # 2. Channels list response
        mock_youtube.channels().list().execute.return_value = {
            "items": [
                {
                    "id": "UC123",
                    "snippet": {"title": "Ayurveda Guru", "description": "guru@example.com"},
                    "statistics": {"subscriberCount": "150000"},
                    "brandingSettings": {}
                },
                {
                    "id": "UC456",
                    "snippet": {"title": "Patanjali Ayurved"},
                    "statistics": {"subscriberCount": "5000000"},
                    "brandingSettings": {}
                },
                {
                    "id": "UC789",
                    "snippet": {"title": "Himalaya Wellness"},
                    "statistics": {"subscriberCount": "800000"},
                    "brandingSettings": {}
                },
                {
                    "id": "UC000",
                    "snippet": {"title": "Dr. Priya Sharma Ayurveda"},
                    "statistics": {"subscriberCount": "200000"},
                    "brandingSettings": {}
                },
                {
                    "id": "UC111",
                    "snippet": {"title": "The Ayurveda Company"},
                    "statistics": {"subscriberCount": "100000"},
                    "brandingSettings": {}
                },
                {
                    "id": "UC222",
                    "snippet": {"title": "Ayurveda With Nidhi"},
                    "statistics": {"subscriberCount": "50000"},
                    "brandingSettings": {}
                }
            ]
        }

        influencers = self.outreach.find_influencers("digestion")
        
        # Verify filtering results
        if isinstance(influencers, dict):
            print(f"ERROR RETURNED: {influencers}")
            assert False, f"find_influencers returned an error: {influencers.get('error')}"
            
        names = [inf["name"] for inf in influencers]
        print(f"Names found: {names}")
        
        assert "Ayurveda Guru" in names
        assert "Dr. Priya Sharma Ayurveda" in names
        assert "The Ayurveda Company" in names
        assert "Ayurveda With Nidhi" in names
        
        assert "Patanjali Ayurved" not in names
        assert "Himalaya Wellness" not in names
        
        assert len(names) == 4

    def test_generate_pitch(self):
        influencer = {
            "name": "Ayurveda Guru",
            "recent_videos": ["How to fix digestion naturally"]
        }
        pitch = self.outreach.generate_pitch(influencer)
        
        assert "Subject:" in pitch
        assert len(pitch.split()) < 150

    def test_format_whatsapp_result(self):
        influencers = [{
            "name": "Ayurveda Guru",
            "subscribers": "150.0K",
            "relevance_score": 9,
            "email": "guru@example.com",
            "recent_videos": ["How to fix digestion naturally"]
        }]
        
        formatted = self.outreach.format_whatsapp_result(influencers)
        
        assert "TOP YOUTUBE CREATORS" in formatted
        assert "Ayurveda Guru" in formatted
        assert "150.0K" in formatted

    def test_quota_error_handling(self):
        from googleapiclient.errors import HttpError
        
        mock_youtube = MagicMock()
        self.outreach.youtube = mock_youtube
        
        # Mock a 403 Quota Exceeded error
        resp = MagicMock()
        resp.status = 403
        mock_youtube.search().list().execute.side_effect = HttpError(resp, b"Quota Exceeded")
        
        result = self.outreach.find_influencers("test")
        assert result["type"] == "quota_exceeded"
        
        formatted = self.outreach.format_whatsapp_result(result)
        assert "Quota Exceeded" in formatted

if __name__ == "__main__":
    t = TestPROutreach()
    t.setup_method()
    
    print("Running PR Outreach tests...")
    
    try:
        t.test_find_influencers_mock()
        print("✅ find_influencers test passed")
        
        t.test_generate_pitch()
        print("✅ generate_pitch test passed")
        
        t.test_format_whatsapp_result()
        print("✅ format_whatsapp_result test passed")
        
        t.test_quota_error_handling()
        print("✅ Error handling test passed")
        
        print("\n🎉 ALL PR OUTREACH TESTS PASSED!")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
