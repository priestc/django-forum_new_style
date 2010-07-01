from django.test import TestCase

class SimpleTest(TestCase):
    def test_rss_order(self):
        """
        Tests that the posts rss feeds get returned in the right order
        """
        
        from forum_new_style.feeds import ThreadPostFeed
        
        
        
