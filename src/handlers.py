import os
import urllib
import datetime

from google.appengine.api import users
from google.appengine.api.mail import send_mail
from google.appengine.ext import db, webapp
from google.appengine.ext.webapp import RequestHandler, template
from google.appengine.ext.webapp.util import run_wsgi_app

import utils

from models import Award, Badge, Hacker, NewsArticle

get_path = utils.path_getter(__file__)

class BaseHandler(RequestHandler):
    login_required = False
    tag_line = 'Next meeting: 17/2/2011'
    title = None
    
    def render_template(self, template_name, template_dict=None):
        if template_dict is None:
            template_dict = {}
        
        user = Hacker.get_current_hacker()
        
        if user:
            if self.login_required:
                redirect_target = '/'
            else:
                redirect_target = self.request.path
            url_creator = users.create_logout_url
        else:
            redirect_target = '/login?url=%s' % self.request.path
            url_creator = users.create_login_url
            
        defaults = {
            'user': user,
            'log_url': url_creator(redirect_target),
            'tag_line': self.tag_line,
            'title': self.title
        }
        
        for key in defaults:
            if key not in template_dict:
                template_dict[key] = defaults[key]
        
        template_path = get_path(
            os.path.join('templates', '%s.html' % template_name))
        self.response.out.write(
            template.render(template_path, template_dict))


class AccountPage(BaseHandler):
    login_required = True
    title = 'Account'
    
    valid_letters = (
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
    
    banned_names = {
        u'neo': "Fat chance are you Neo. If you are, I'm not gona get my hopes up",
        }
    
    
    def post(self):
        if len(self.request.POST) == 3 and 'handle' in self.request.POST \
                and 'real_name' in self.request.POST \
                and 'email' in self.request.POST:
            
            handle = self.request.POST.getall('handle')[0]
            template_dict = {}
            hacker = Hacker.get_current_hacker()
            other = Hacker.gql('WHERE handle = :1', handle).get()
            
            if (not handle or len(handle) > 12 or
                any(l not in self.valid_letters for l in handle)):
                template_dict['error'] = 'Pick something sensible, you moron.'
            
            elif other and other.user_id != hacker.user_id:
                template_dict['error'] = 'Sorry, already taken.'
            
            elif handle.lower() in self.banned_names:
                template_dict['error'] = self.banned_names[handle]
            
            else:
                real_name = self.request.POST.getall('real_name')[0]
                if real_name:
                    hacker.real_name = real_name
                email = self.request.POST.getall('email')[0]
                if email:
                    hacker.email = email
                hacker.handle = handle
                hacker.save()
                template_dict['error'] = 'Profile updated'
            self.render_template('account', template_dict=template_dict)
            
    def get(self):
        self.render_template('account')

class AdminPage(BaseHandler):
    login_required = True
    def post(self):
        post =  self.request.POST
        if post['kind'] == 'badge':
            b = Badge(name=post['name'], description=post['description'], 
                      category=post['category'], image=post['image'],
                      value=int(post['value']))
            b.save()
        elif post['kind'] == 'article':
            a = NewsArticle(title=post['title'], author=post['author'],
                             body=post['body'], date=datetime.date.today())
            a.save()
        elif post['kind'] == 'award':
            badge = Badge.gql('WHERE name = :1', post['badge']).get()
            for h in post.getall('hackers'):
                hacker = Hacker.gql('WHERE handle = :1', h).get()
                a=Award(hacker=hacker, 
                        badge=badge,
                        date=datetime.date.today(),
                        proof=post['proof'])
                a.save()
                hacker.score_cache = hacker.score + badge.value
                hacker.save()
        self.get()
            
    def get(self):
        self.render_template('admin', {'badges': Badge.all(),
                                       'hackers': Hacker.all()})
        
class BadgePage(BaseHandler):
    def get(self, name):
        query = Badge.gql('WHERE name = :1', urllib.unquote(name))
        badge = iter(query).next() if query.count() else None
        self.render_template('badge', {'badge': badge})

class BadgeApplicationHandler(BaseHandler):
    login_required = True
    
    def post(self):
        post = self.request.POST
        if len(post) == 2 and 'badge' in post and 'proof' in post:
            body = 'Hacker: %s\nBadge: %s\nProof:\n%s' % (
                Hacker.get_current_hacker().handle, post['badge'], 
                post['proof'])
            send_mail(
                sender='petersutton2009@gmail.com',
                to='petersutton2009@gmail.com',
                subject='Badge application',
                body=body)
            self.render_template('badge_application', template_dict={'message':
                'Application submitted. It will be reviewed as soon as possible.'})
        
    def get(self):
        selected_badge = self.request.GET.getall('badge')
        if selected_badge:
            selected_badge = selected_badge[0]
        else:
            selected_badge = None
        
        badges = Badge.gql('ORDER BY name')
        self.render_template('badge_application', template_dict={'badges':badges,
            'selected_badge': selected_badge})
    

class BadgesPage(BaseHandler):
    title = 'Badges'
    def get(self):
        order = self.request.GET.get('order', 'value')
        if order == 'receivers':
            b = list(Badge.all())
            b.sort(key=lambda i:i.awards.count())
        else:
            b = Badge.gql('ORDER BY ' + order)
        self.render_template('badges', {'badges': b})


class CalendarPage(BaseHandler):
    def get(self):
        self.render_template('calendar')


class ContactPage(BaseHandler):
    def get(self):
        self.render_template('contact')

class FAQPage(BaseHandler):
    def get(self):
        self.render_template('faq')

class ManualPage(BaseHandler):
    def get(self):
        self.render_template('manual')

# This handler is a hack to force people to select handles.
class LoginHandler(BaseHandler):
    def get(self):
        if 'url' in self.request.GET:
            hacker = Hacker.get_current_hacker()
            if hacker.handle.isdigit() and len(hacker.handle) == 21:
                self.redirect('/account')
            else:
                self.redirect(self.request.GET.getall('url')[0])
        else:
            self.redirect('/')


class MembersPage(BaseHandler):
    def get(self):
        hackers = list(Hacker.all())
        if hackers:
            hackers.sort(key=lambda h:(h.score,h.handle))
            rank = 0
            ranked_hackers = [(rank, hackers[-1])]
            for i in range(len(hackers)-2, 0, -1):
                if hackers[i + 1].score_cache != hackers[i].score_cache:
                    rank += 1
                ranked_hackers.append((rank, hackers[i]))
            
        self.render_template('members', {'hackers': ranked_hackers})

        
class MemberPage(BaseHandler):
    def get(self, handle):
        query = Hacker.gql('WHERE handle = :1', urllib.unquote(handle))
        hacker = iter(query).next() if query.count() else None
        self.render_template('member', {'hacker': hacker})

class MessagesHandler(BaseHandler):
    def get(self, message_index=None):
        message_path = 'static/messages/%s.html' % message_index
        self.response.out.write(open(message_path).read())

class NewsPage(BaseHandler):
    def get(self):
        news_articles = NewsArticle.gql('ORDER BY date DESC')
        self.render_template('news', {'news_articles': news_articles})


class ProjectsPage(BaseHandler):
    def get(self):
        self.render_template('projects')