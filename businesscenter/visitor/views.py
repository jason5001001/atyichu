# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import random
from urllib import quote_plus
from django.utils.translation import ugettext as _
from django.utils import timezone
from django.contrib.auth import login, logout, authenticate, \
    update_session_auth_hash
from django.core.urlresolvers import reverse
from django.core.mail import mail_admins
from django.core.cache import cache
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, list_route
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from .serializers import VisitorSerializer, VisitorExtraSerializer,\
    VisitorCreateSerializer, VisitorProfileSerializer, VisitorLoginSerializer
from .oauth2 import WeixinBackend, WeixinQRBackend
from .models import Visitor, VisitorExtra
from .permissions import IsVisitorSimple, IsVisitorOrReadOnly
from .extra_handlers import PendingUserStore
from .sms import TaoSMSAPI
from utils.serializers import UserPasswordSerializer


@api_view(['POST'])
@permission_classes((AllowAny,))
def login_view(request):
    # USE openid
    status = 400
    backend = 'weixin'
    try:
        extra = VisitorExtra.objects.get(openid=request.data['weixin'],
                                         backend=backend)
        serializer = VisitorSerializer(instance=extra.weixin.visitor)
        user_data = serializer.data
        user = authenticate(weixin=extra.openid)
        login(request, user)
    except KeyError as e:
        user_data = {'weixin': _('Missed param')}
    except Visitor.DoesNotExist:
        user_data = {'weixin': _('User does not exists')}
    except Exception as e:
        user_data = {'error': e.message}
    else:
        status = 200
    return Response(user_data, status=status)


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
    """ OAuth2 auhentication with Weixin (Wechat).
        Params:
            qr: if it has some value that can be interpreted like True,
                then we use qr code for authentication.
                Required for the desktop clients.
    """
    url = request.GET.get("qr", "1")
    weixin_oauth2 = WeixinBackend()
    redirect_url = '{}://{}{}'.format(request.scheme,
                                      request.get_host(),
                                      reverse('visitor:openid'))
    redirect_url += '?url={}'.format(url)
    url = weixin_oauth2.get_authorize_uri(redirect_url)
    return HttpResponseRedirect(url)


def openid(request):
    """ OAuth2 handler for weixin """
    redirect = reverse('index')
    qr = request.GET.get("qr", None)
    response = HttpResponseRedirect(redirect + '#!/')

    if request.user.is_authenticated():
        return response

    code = request.GET.get("code", None)
    if not code:
        return JsonResponse({'error': _('You don`t have weixin code.')})

    if qr:
        weixin_oauth = WeixinQRBackend()
        backend = 'weixin_qr'
    else:
        weixin_oauth = WeixinBackend()
        backend = 'weixin'
    try:
        token_data = weixin_oauth.get_access_token(code)
    except TypeError:
        return JsonResponse({'error': _('You got error trying to get openid')})

    user_info = weixin_oauth.get_user_info(token_data['access_token'],
                                           token_data['openid'])
    data = {'avatar_url': user_info.get('headimgurl'),
            'nickname': user_info.get('nickname'),
            'unionid': token_data['unionid'],
            'extra': {
                'openid': token_data['openid'],
                'access_token': token_data['access_token'],
                'expires_in': token_data['expires_in'],
                'refresh_token': token_data['refresh_token'],
                'backend': backend,
            }
    }

    try:
        extra = VisitorExtra.objects.get(openid=token_data['openid'],
                                         backend=backend)
        s = VisitorExtraSerializer(instance=extra, data=data['extra'],
                                   partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        visitor = extra.weixin.visitor
        # Remove after WIPE
        visitor_data = {'nickname': data['nickname'],
                        'unionid': data['unionid']}

        visitor_s = VisitorSerializer(instance=visitor, data=visitor_data,
                                      partial=True)
        visitor_s.is_valid(raise_exception=True)
        visitor = visitor_s.save()
    except VisitorExtra.DoesNotExist:
        serializer = VisitorSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        visitor = serializer.save()
        extra = None

    if not extra:
        extra = visitor.weixin.visitorextra_set.get(backend=backend)
    user = authenticate(weixin=extra.openid, backend=backend)
    login(request, user)
    return response


@api_view(['POST'])
@permission_classes((IsVisitorSimple,))
def update_visitor(request):
    """ Updating user data from weixin. Sync """
    # TODO: TEST
    qr = request.data.get('qr', None)
    if qr:
        wx = WeixinQRBackend()
        backend = 'weixin_qr'
    else:
        wx = WeixinBackend()
        backend = 'weixin'
    visitor = request.user.visitor
    extra = VisitorExtra.objects.get(weixin=visitor.weixin, backend=backend)
    data = {'access_token': extra.access_token,
            'openid': extra.openid}
    if extra.is_expired():
        data.update(wx.refresh_user_credentials(extra.refresh_token))
        s = VisitorExtraSerializer(instance=extra, data=data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
    user_info = wx.get_user_info(data['access_token'], data['openid'])
    user_data = {
        'avatar_url': user_info.get('headimgurl'),
        'nickname': user_info.get('nickname'),
    }
    serializer = VisitorSerializer(instance=visitor,
                                   data=user_data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(data=serializer.data)


@api_view(['GET'])
@permission_classes((IsVisitorSimple,))
def get_me(request):
    """ Provides personal user data, username and thumb """
    visitor = request.user.visitor
    serializer = VisitorSerializer(instance=visitor)
    return Response(data=serializer.data)


def test_auth(request):
    host = request.get_host()
    if host == '127.0.0.1:8000':
        extra = VisitorExtra.objects.get(backend='weixin', openid='weixin')
        user = authenticate(weixin=extra.openid)
        login(request, user)
        response = HttpResponseRedirect('/#!/')
        return response
    raise PermissionDenied


class ProfileViewSet(viewsets.GenericViewSet):
    """
    A simple ViewSet for listing or retrieving visitors.
    """
    permission_classes = (IsVisitorOrReadOnly,)

    def get_serializer_class(self):
        serializer_map = {
            'retrieve': VisitorProfileSerializer,
            'create': VisitorCreateSerializer,
            'edit': VisitorProfileSerializer,
            'change_password': UserPasswordSerializer,
            'login': VisitorLoginSerializer,
            'login_start': VisitorLoginSerializer,
            'login_end': VisitorLoginSerializer,
            'me': VisitorProfileSerializer,
        }
        return serializer_map[self.action]

    def get_queryset(self):
        return Visitor.objects.all()

    def retrieve(self, request, pk=None):
        """ retreive visitor information, may be useless. """
        queryset = self.get_queryset()
        visitor = get_object_or_404(queryset, pk=pk)
        serializer = self.get_serializer(visitor)
        return Response(serializer.data)

    @list_route(methods=['get'])
    def me(self, request):
        queryset = self.get_queryset()
        visitor = get_object_or_404(queryset, pk=request.user.id)
        serializer = self.get_serializer(visitor)
        return Response(serializer.data)

    def create(self, request):
        """ Create user. Redirect to get_me"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visitor = serializer.save()
        user = authenticate(phone=visitor.phone,
                            password=request.data['password'])
        login(request, user)
        url = reverse('visitor:me')
        return HttpResponseRedirect(url)

    @list_route(methods=['patch'])
    def edit(self, request):
        """ PK not suplied visitor instance takes from request.user."""
        user = request.user
        # maybe following line is redundant
        self.check_object_permissions(request, user.visitor)
        serializer = self.get_serializer(instance=user.visitor,
                                         data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @list_route(methods=['post'])
    def change_password(self, request):
        """ Change user`s password. PK not supplied."""
        user = request.user
        self.check_object_permissions(request, user.visitor)
        serializer = self.get_serializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        update_session_auth_hash(request, user)
        return Response(status=204)

    @list_route(methods=['post'])
    def login(self, request):
        """
        Handles login visitor by phone number
        """
        # TODO: Add verification code handling
        status = 400
        s = self.get_serializer(data=self.request.data)
        s.is_valid(raise_exception=True)
        try:
            user = authenticate(phone=s.data['phone'],
                                password=s.data['password'])
            serializer = VisitorSerializer(instance=user.visitor)
            data = serializer.data
            login(request, user)
        except Exception as e:
            data = {'error': e.message}
        else:
            status = 200
        return Response(data, status=status)

    @list_route(methods=['post'])
    def login_start(self, request):
        """
                Handles login visitor by phone number
                """
        # TODO: Add verification code handling
        status = 400
        s = self.get_serializer(data=self.request.data)
        s.is_valid(raise_exception=True)
        try:
            user = authenticate(phone=s.data['phone'],
                                password=s.data['password'])
            # create a session key manually, because django does not create
            #  a session for anonymous user
            pending_store = PendingUserStore()
            code = pending_store.add_by_sessionid(request, user)
            phone = s.data['phone']
        except Exception as e:
            data = {'error': e.message}
        else:
            sms_api = TaoSMSAPI(settings.TAO_SMS_KEY, settings.TAO_SMS_SECRET)
            r = sms_api.send_code(phone, code)
            mail_admins('tao response', str(r))
            status = 200
            data = {'status': 'sent'}
        return Response(data, status=status)

    @list_route(methods=['post'])
    def login_end(self, request):
        """ Verification code is required. """
        try:
            code = request.data['code']
            sessionid = request.session.session_key

            pending_store = PendingUserStore()
            user = pending_store.get_by_sessionid(sessionid, code)
        except KeyError:
            raise ValidationError({'detail':
                                       _('Verification code is required!')})
        else:
            login(request, user)
            url = reverse('visitor:me')
            return HttpResponseRedirect(url)
