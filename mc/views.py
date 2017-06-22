from django.shortcuts import render, redirect
from sklearn.externals import joblib
import praw
import datetime
from operator import attrgetter
import sys
import numpy as np
from mc.forms import subs, EmailNewPass, Usersubs
from mc.models import UserList
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache


class Post:
        def __init__(self, subreddit, author, title, score, numOfComments, permalink, diff_minutes):
                self.subreddit = subreddit
                self.author = author
                self.title = title
                self.score = score
                self.numOfComments = numOfComments
                self.permalink = permalink
                self.diff_minutes = diff_minutes

class HotPost:
        def __init__(self, subreddit, title, permalink, rating):
                self.subreddit = subreddit
                self.title = title
                self.permalink = permalink
                self.rating = rating


reddit = praw.Reddit(client_id='T8UpP-8cdy96BQ',
                     client_secret="7sms5L2o9JB8w1Bf6WRFDJ_8X6Q",
                     user_agent='pythonscript:com.example.frontandrisingchecker:v0.1 (by /u/connlloc)',
                     username='connlloc',
                     password='tiotan12')

svm = joblib.load('/home/connlloc/sites/mc/modelSvm.pkl')
trendingPosts = []

def email(request):
    if request.method == 'POST':       
        form = EmailNewPass(request.POST)
        if form.is_valid():
            email = form.cleaned_data['aemail']
            e = TheEmails(emails=email)
            e.save()
            emailSaved = True
            form = subs()
            return render(request, 'home.html',{'form':form, 'emailSaved':emailSaved})
    else:
        form = subs()
        emailSaved = False
        return render(request, 'home.html',{'form':form, 'emailSaved':emailSaved})

@never_cache
@login_required(login_url='/sign_page/')
def userView(request):
    
    try:
        customlist = UserList.objects.filter(username=request.user.username)
        print(customlist)
    except:
        customlist = None

    
    trendingPosts = []
    if request.method == 'POST':
        form = subs(request.POST)
        if form.is_valid():
            subreddit = form.cleaned_data['subreddits']

            subreddits = subreddit.split(',')
            if len(subreddits) > 1:
                for subreddit in subreddits:
	            TrendingPosts = returnTrending(subreddit, trendingPosts)

            else:
                trendingPosts = returnTrending(subreddit, trendingPosts)

            for post in trendingPosts:
                post.rating=post.rating * 100 
                post.rating = round(post.rating, 2)
        form = Usersubs()
        return render(request,'user.html', {'Posts':trendingPosts,'form':form,'customlist':customlist})
    form = Usersubs()

    return render(request,'user.html', {'Posts':trendingPosts,'form':form,'customlist':customlist})


@never_cache
@login_required(login_url='/sign_page/')
def deleteList(request, listuuid):
    l = UserList.objects.get(listuuid=listuuid)
    if request.user.username == l.username:
        l.delete()
    return redirect('/user-list/')

@never_cache
@login_required(login_url='/sign_page/')
def userList(request):
    try:
        customlist = UserList.objects.filter(username=request.user.username)
       
    except:
        customlist = []

    l=None   
    if request.method == 'POST' and len(customlist) <= 10:
        subs = request.POST.getlist('subreddits')
        label = request.POST.get('label')
        if len(subs) <= 10:
            itemlist = ''
            counter = False
            for item in subs:
                if item:
                    if counter == False:
                        counter = True
                        itemlist = itemlist + item
                    else:
                        itemlist = itemlist + ',' + item               
        l = UserList(username=request.user.username,subreddits=itemlist,label=label)
        l.save()
        try:
            customlist = UserList.objects.filter(username=request.user.username)
        
        except:
            customlist = []

        request.method = 'GET'
        return render(request, 'userlist.html',{'customlist':customlist})
    return render(request, 'userlist.html',{'customlist':customlist})

@never_cache
def home(request):
    trendingPosts = []


    if request.method == 'POST':
        form = subs(request.POST)
        if form.is_valid():
            subreddit = form.cleaned_data['subreddits']

            subreddits = subreddit.split(',')
            if len(subreddits) > 1:
                for subreddit in subreddits:
	            TrendingPosts = returnTrending(subreddit, trendingPosts)

            else:
                trendingPosts = returnTrending(subreddit, trendingPosts)

            for post in trendingPosts:
                post.rating=post.rating * 100 
                post.rating = round(post.rating, 2)
        form = subs()
        return render(request,'home.html', {'Posts':trendingPosts,'form':form})
    form = subs()
    return render(request,'home.html', {'Posts':trendingPosts,'form':form})



def returnTrending(subreddit, trendingPosts):

    fillers = []
    for submission in reddit.subreddit(subreddit).new(limit=75):
        author = submission.author
        title = submission.title
        score = submission.score
        numOfComments = submission.num_comments
        permalink = submission.permalink
        timeCreated = submission.created_utc

        timeOfPost = datetime.datetime.utcfromtimestamp(timeCreated)
        timeNow = datetime.datetime.utcnow()

        diff = timeNow - timeOfPost
        diff_minutes = (diff.days * 24 * 60) + (diff.seconds/60)

        if diff_minutes == 0:
            diff_minutes = 1 
        if diff_minutes < 140:
            fillers.append(Post(subreddit, author, title, score, numOfComments, permalink, diff_minutes))

    for filler in fillers:
        numberOfHotterPostsInSub = 0
        for filler2 in fillers:
           if filler.score/filler.diff_minutes > filler2.score/filler2.diff_minutes:                                              
               numberOfHotterPostsInSub = numberOfHotterPostsInSub + 1

        prediction = svm.predict_proba([[filler.score,filler.numOfComments,filler.diff_minutes,numberOfHotterPostsInSub]])
        if len(trendingPosts) >= 15:
           if trendingPosts[14].rating < prediction[0][1]:
               trendingPosts.pop()
               trendingPosts.append(HotPost(filler.subreddit, filler.title, "http://www.reddit.com/" + filler.permalink, prediction[0][1]))
               trendingPosts.sort(key=lambda x: x.rating, reverse=True)
        else:
            trendingPosts.append(HotPost(filler.subreddit, filler.title, "http://www.reddit.com/" + filler.permalink, prediction[0][1]))
            if len(trendingPosts) == 15:
                trendingPosts.sort(key=lambda x: x.rating, reverse=True)
       
    return trendingPosts


