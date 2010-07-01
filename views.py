from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template.defaultfilters import slugify
from django.template import RequestContext
from django.conf import settings
from django.contrib.auth.models import User

from captcha import get_captcha_error

from models import Forum, Thread, Post
from forms import PostForm, ThreadForm, render_new_form

def index(request):
    """
    Render the forum index page
    """
    
    return render_to_response('forum/index.html',
                              {'forums': Forum.objects.all()},
                              context_instance=RequestContext(request))

def thread_view(request, id, slug):
    """
    Render the thread and all the posts in it
    """
    
    thread = get_object_or_404(Thread, pk=id)
    captcha_error = ''
    errors = None
    
    if "-" + slugify(thread.title) != slug:
        # slug does not match, redirect to the correct slug
        return HttpResponseRedirect(thread.get_absolute_url())
        
    if request.POST:
        result = new_post(request, thread=thread, user=request.user)
        
        if result.errors:
            # some errors occured, reuse all form objects
            postform = result.postform
            captcha_error = result.captcha_error
    
    if not request.POST or not result.errors:
        if thread.forum.force_anon:
            default_user = None
        else:
            default_user = request.user.id
            
        postform = PostForm()
    
    c = {'posts': thread.post_set.all(),
         'thread': thread,
         'forum': thread.forum,
         'new_form': render_new_form(postform=postform,
                                      user=request.user,
                                      captcha_error=captcha_error)}
                     
    return render_to_response('forum/thread.html', c,
                              context_instance=RequestContext(request))




def forum_view(request, id, slug):
    """
    Render the forum (the thread list), also handle the new thread form
    """
    
    forum = get_object_or_404(Forum, pk=id)
    captcha_error = ''
    
    if request.POST:
        result = new_thread(request, forum=forum, user=request.user)
    
        if result.errors:
            threadform = result.threadform
            postform = result.postform
            captcha_error = result.captcha_error
        else:
            # this function was called after a new thread was made, instead of
            # returning back to the forum page, redirect to the newly
            # created thread
            return HttpResponseRedirect(result.thread.get_absolute_url())
    
    if not request.POST or not result.errors:
        postform = PostForm()
        threadform = ThreadForm()
    
    if "-" + slugify(forum.name) != slug:
        # slug does not match, redirect to the correct slug
        return HttpResponseRedirect(forum.get_absolute_url())
    
    threads = forum.threads_by_bumped()
    
    c = {'threads': threads,
         'forum': forum,
         'new_form': render_new_form(postform=postform,
                                     threadform=threadform,
                                     user=request.user,
                                     captcha_error=captcha_error)}
                     
    return render_to_response('forum/forum.html', c,
                              context_instance=RequestContext(request))


###############################
## all edit/new aux views below
###############################

class Result(object):
    captcha_error = ''
    threadform = ''
    postform = ''
    thread = None
    post = None
    forum = None
    captcha_success = False
    
    def errors(self):
        """
        Did the new thread/post routine have any errors?
        """
        
        if self.threadform:
            valid = self.threadform.is_valid()
        else:
            valid = True
          
        valid = valid and self.postform.is_valid() and not self.captcha_error
        return not valid
        
    errors = property(errors)
    
def new_thread(request, forum, user):
    """
    Given a POST dict, create a new thread, then pass whats left to the 
    new_post function and then create the op. This function returns any
    errors, it returns None if there are no errors.
    """
    
    threadform = ThreadForm(request.POST)
    result = Result()
    result.threadform = threadform
    
    captcha_error = get_captcha_error(request)
    
    if captcha_error:
        result.captcha_error = captcha_error
        result.postform = PostForm(request.POST)
        return result
    else:
        result.captcha_success = True
    
    if threadform.is_valid():
        data = threadform.cleaned_data
        thread = Thread(title=data['title'], forum=forum)
        thread.save()
        result.thread = thread
    else:
        # error occured, return the form and the captcha error
        # (already set to result object) don't bother to try to add the post
        return result
    
    # all is valid, now make the op, skip captcha part 
    # because we already checked it
    return new_post(request, thread, user, result=result)
    
    
def new_post(request, thread, user, result=None):
    """
    Handle the new post form data when it gets posted
    """

    if not result:
        result = Result()
        
    postform = PostForm(request.POST)
    result.postform = postform
    
    if not result.captcha_success:
        captcha_error = get_captcha_error(request)
        if captcha_error:
            result.captcha_error = captcha_error
            return result
    
    if postform.is_valid():
        data = postform.cleaned_data
        post = Post(body=data['body'], thread=thread)
        
        #######
        
        if data['spam_prevent']:
            # if the spam prevent field is not blank, assume the post was made
            # by a spambot
            return HttpResponse('plz go away spambot thx')
        
        #######
        
        if not user.is_authenticated() or data['as_anon']:
            # anonymously posted messages are annotated with the poster's
            # IP address so they can edit them later
            post.ip = request.META['REMOTE_ADDR']
            post.as_anon = True
        else:
            #post.ip = "0.0.0.0"
            post.user = user
            post.as_anon = False
        
        ########
        
        if data['as_admin']:
            # this post was made by an admin and the post will be displayed
            # ina  way that lets everyone know that this person is an admin
            post.as_admin = True
        
        ########
        
        post.save()
        result.post = post
        

    return result

def delete_post(request, id, timehash):
    post = get_object_or_404(Post, pk=id)
    
    # get the forum so we know where to redirect to
    forum = Forum.objects.get(thread__post=post)
    
    if post.posted_time.microsecond == int(timehash):
        if post.thread.post_count() == 1:
            post.thread.delete()
        post.delete()
        
    if post.thread.pk:
        # thread still exists, go there
        redirect = post.thread.get_absolute_url()
    else:
        # thread no longer exists, redirect to the forum
        redirect = forum.get_absolute_url()
        
    return HttpResponseRedirect(redirect)



def edit_post(request, id, timehash):
    post = get_object_or_404(Post, pk=id)
    if not post.posted_time.microsecond == int(timehash):
        raise Http404
        
    if request.POST:
        form = PostForm(request.POST, instance=post)
    else:
        form = PostForm(instance=post)
        
    return render_to_response('forum/edit.html',
                              {'form': form},
                              context_instance=RequestContext(request))











