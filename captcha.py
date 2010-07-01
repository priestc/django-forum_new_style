from django.conf import settings

try:
    from recaptcha.client import captcha
except ImportError:
    captcha = None
    
def get_captcha_error(request):
    """
    Check to see that the captcha has validated, if there are errors, it
    returns those errors. No errors returns None. If recaptcha is not installed
    it always returns no errors. If the user is authenticated, it always returns
    no errors.
    """
    
    if settings.FORUM_USE_RECAPTCHA and captcha and not request.user.is_authenticated():
        captcha_response = captcha.submit(
                request.POST.get("recaptcha_challenge_field", None),
                request.POST.get("recaptcha_response_field", None),
                settings.RECAPTCHA_PRIVATE_KEY,
                request.META.get("REMOTE_ADDR", None))
        
        if not captcha_response.is_valid:
            return "&error=%s" % captcha_response.error_code
    
    return None
