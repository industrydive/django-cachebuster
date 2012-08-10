__author__ = 'James Addison'

import posixpath
import datetime
import urllib
import os

from django import template
from django.conf import settings

register = template.Library()


@register.tag(name="media")
def do_media(parser, token):
    return CacheBusterTag(token, True)


@register.tag(name="static")
def do_static(parser, token):
    return CacheBusterTag(token, False)


class CacheBusterTag(template.Node):
    def __init__(self, token, is_media):
        self.is_media = is_media

        try:
            tokens = token.split_contents()
        except ValueError:
            raise template.TemplateSyntaxError, "'%r' tag must have one or two arguments" % token.contents.split()[0]

        self.path = tokens[1]
        self.force_timestamp = len(tokens) == 3 and tokens[2] or False
        self._finders = False

    def render(self, context):
        # self.path may be a template variable rather than a simple static file string
        try:
            path = template.Variable(self.path).resolve(context)
        except template.VariableDoesNotExist:
            path = self.path

        path = posixpath.normpath(urllib.unquote(path)).lstrip('/')

        if self.is_media:
            url_prepend = settings.MEDIA_URL
            unique_prepend = getattr(settings, 'CACHEBUSTER_PREPEND_MEDIA', False)
            unique_string = self.get_file_modified(os.path.join(settings.MEDIA_ROOT, path))
        else:
            # django versions < 1.3 don't have a STATIC_URL, so fall back to MEDIA_URL
            url_prepend = getattr(settings, "STATIC_URL", settings.MEDIA_URL)
            unique_prepend = getattr(settings, 'CACHEBUSTER_PREPEND_STATIC', False)

            absolute_path = None
            if settings.DEBUG and ('staticfiles' in settings.INSTALLED_APPS or 'django.contrib.staticfiles' in settings.INSTALLED_APPS):
                if self._finders is False:
                    # finders won't exist if we're not using Django 1.3+
                    # Give preference to a standalone version of staticfiles
                    # over the contrib version.
                    # This has been moved into the body of the class because
                    # of a compile time race condition with settings.
                    try:
                        from staticfiles import finders
                        self._finders = finders
                    except ImportError, e:
                        print "ERROR importing staticfiles.finders: %s" % e
                        try:
                            from django.contrib.staticfiles import finders
                        except ImportError, err:
                            print "ERROR importing django.contrib.staticfiles.finders: %s" % err
                            self._finders = None
                absolute_path = self._finders.find(path) if self._finders else None

            if absolute_path is None:
                # django versions < 1.3 don't have a STATIC_ROOT, so fall back to MEDIA_ROOT
                absolute_path = os.path.join(getattr(settings, 'STATIC_ROOT', settings.MEDIA_ROOT), path)

            if self.force_timestamp:
                unique_string = self.get_file_modified(absolute_path)
            else:
                unique_string = getattr(settings, 'CACHEBUSTER_UNIQUE_STRING', None)
                if not unique_string:
                    unique_string = self.get_file_modified(absolute_path)

        # Add in harder cachebusting required for CloudFront et al
        if unique_prepend:
          return url_prepend + unicode(unique_string) + '/' + path
        else:
          return url_prepend + path + '?' + unicode(unique_string)

    def get_file_modified(self, path):
        try:
            return datetime.datetime.fromtimestamp(os.path.getmtime(os.path.abspath(path))).strftime('%S%M%H%d%m%y')
        except:
            # if the file can't be found, return this; it will be an
            # indicator to the developer that collectstatic needs to be run
            # (as if the resulting 404 for the missing file wouldn't be)
            return '000000000000'
