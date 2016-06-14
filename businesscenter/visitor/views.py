from __future__ import unicode_literals

from urllib import quote_plus
from django.utils.translation import ugettext as _
from django.utils import timezone
from django.contrib.auth import login, logout, authenticate
from django.core.urlresolvers import reverse
from django.core.mail import send_mail, mail_admins
from django.http import HttpResponseRedirect, JsonResponse

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from .serializers import WeixinSerializer
from .oauth2 import WeixinBackend
from .models import Visitor
from utils.permissions import IsVisitorSimple


@api_view(['POST'])
@permission_classes((AllowAny,))
def login_view(request):
    # USE openid
    # ALSO with captcha look pretty stupid
    serializer = WeixinSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    visitor = serializer.save()
    user = authenticate(weixin=visitor.weixin)
    user_data = serializer.data
    try:
        login(request, user)
    except Exception as e:
        user_data = {'error': e.message}
    return Response(user_data, status=200)


@api_view(['GET'])
@permission_classes((AllowAny,))
def is_authenticated(request):
    if request.user.is_authenticated() \
            and hasattr(request.user, 'visitor'):
        r = True
    else:
        r = False
    return Response({'is_authenticated': r})


@api_view(['GET'])
@permission_classes((AllowAny,))
def logout_view(request):
    logout(request)
    return Response(status=200)


@api_view(['GET', 'POST'])
@permission_classes((AllowAny,))
def verify_captcha(request, captcha_key, captcha_value):
    """ PIN VERIFICATION. NO USE FOR NOW """
    # THAT LOGIC LOOKS STUPID. But I leave it for now.
    data = {}
    status = 400
    if not captcha_value:
        data = {'captcha': _('Verification code required')}
    else:
        server_captcha = request.session.get(captcha_key)
        if server_captcha != captcha_value:
            data = {'captcha_error': _('Code is incorrect or has expired')}
        else:
            del request.session[captcha_key]
            status = 200

    return Response(data, status=status)


@api_view(['GET', 'POST'])
@permission_classes((AllowAny,))
def dummy_api(request):
    return Response(data={'message': 'Hello'}, status=200)


def index(request):
    url = request.GET.get("url", "1")
    weixin_oauth2 = WeixinBackend()
    redirect_url = '{}://{}{}'.format(request.scheme,
                                      request.get_host(),
                                      reverse('visitor:openid'))
    redirect_url += '?url={}'.format(url)
    url = weixin_oauth2.get_authorize_uri(redirect_url)
    return HttpResponseRedirect(url)


def openid(request):
    url = request.GET.get("url")

    redirect = reverse('index')

    if url == '2':
        response = HttpResponseRedirect(redirect + '#!/photo/')
    else:
        response = HttpResponseRedirect(redirect + '#!/mirror/')

    if request.user.is_authenticated():
        return response

    code = request.GET.get("code", None)

    if not code:
        return JsonResponse({'error': _('You don`t have weixin code.')})

    weixin_oauth = WeixinBackend()
    try:
        token_data = weixin_oauth.get_access_token(code)
    except TypeError:
        return JsonResponse({'error': _('You got error trying to get openid')})

    user_info = weixin_oauth.get_user_info(token_data['access_token'],
                                           token_data['openid'])
    data = {'avatar_url': user_info.get('headimgurl'),
            'nickname': user_info.get('nickname'),
            'weixin': token_data['openid'],
            'access_token': token_data['access_token'],
            'expires_in': token_data['expires_in'],
            'refresh_token': token_data['refresh_token']}
    try:
        visitor = Visitor.objects.get(weixin=token_data['openid'])
    except Visitor.DoesNotExist:
        serializer = WeixinSerializer(data=data)
    else:
        serializer = WeixinSerializer(instance=visitor, data=data)

    serializer.is_valid(raise_exception=True)
    visitor = serializer.save()
    user = authenticate(weixin=visitor.weixin)
    login(request, user)
    response.set_cookie('weixin', visitor.weixin, max_age=300)
    return response


@api_view(['GET'])
@permission_classes((IsVisitorSimple,))
def get_visitor(request):
    visitor = request.user.visitor
    serializer = WeixinSerializer(instance=visitor)
    return Response(data=serializer.data)


@api_view(['POST'])
@permission_classes((IsVisitorSimple,))
def update_visitor(request):
    """ Updating user data from weixin """
    wx = WeixinBackend()
    visitor = request.user.visitor
    data = {'access_token': visitor.access_token,
            'weixin': visitor.weixin}
    if visitor.is_expired():
        data.update(wx.refresh_user_credentials(visitor.refresh_token))
        mail_admins('From atyichu', str(data))
    user_info = wx.get_user_info(data['access_token'], data['weixin'])
    data.update(user_info)
    serializer = WeixinSerializer(instance=visitor, data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    mail_admins('From atyichu', str(serializer.data))
    return Response(data=serializer.data)
