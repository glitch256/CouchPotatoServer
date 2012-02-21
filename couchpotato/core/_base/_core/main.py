from couchpotato.api import addApiView
from couchpotato.core.event import fireEvent, addEvent
from couchpotato.core.helpers.request import jsonified
from couchpotato.core.helpers.variable import cleanHost, md5
from couchpotato.core.logger import CPLog
from couchpotato.core.plugins.base import Plugin
from couchpotato.environment import Env
from flask import request
from uuid import uuid4
import os
import time
import traceback
import webbrowser

if os.name == 'nt':
    import getppid


log = CPLog(__name__)

class Core(Plugin):

    ignore_restart = ['Core.crappyRestart', 'Core.crappyShutdown']
    shutdown_started = False

    def __init__(self):
        addApiView('app.shutdown', self.shutdown, docs = {
            'desc': 'Shutdown the app.',
            'return': {'type': 'string: shutdown'}
        })
        addApiView('app.restart', self.restart, docs = {
            'desc': 'Restart the app.',
            'return': {'type': 'string: restart'}
        })
        addApiView('app.available', self.available, docs = {
            'desc': 'Check if app available.'
        })

        addEvent('app.crappy_shutdown', self.crappyShutdown)
        addEvent('app.crappy_restart', self.crappyRestart)
        addEvent('app.load', self.launchBrowser, priority = 1)
        addEvent('app.base_url', self.createBaseUrl)
        addEvent('app.api_url', self.createApiUrl)

        addEvent('setting.save.core.password', self.md5Password)
        addEvent('setting.save.core.api_key', self.checkApikey)

        self.removeRestartFile()

    def md5Password(self, value):
        return md5(value) if value else ''

    def checkApikey(self, value):
        return value if value and len(value) > 3 else uuid4().hex

    def available(self):
        return jsonified({
            'succes': True
        })

    def crappyShutdown(self):
        try:
            self.urlopen('%s/app.shutdown' % self.createApiUrl(), show_error = False)
            return True
        except:
            self.initShutdown()
            return False

    def crappyRestart(self):
        try:
            self.urlopen('%s/app.restart' % self.createApiUrl(), show_error = False)
            return True
        except:
            self.initShutdown(restart = True)
            return False

    def shutdown(self):
        self.initShutdown()
        return 'shutdown'

    def restart(self):
        self.initShutdown(restart = True)
        return 'restarting'

    def initShutdown(self, restart = False):
        if self.shutdown_started:
            log.info('Already shutting down')

        log.info('Shutting down' if not restart else 'Restarting')

        self.shutdown_started = True

        fireEvent('app.shutdown')
        log.debug('Every plugin got shutdown event')

        loop = True
        while loop:
            log.debug('Asking who is running')
            still_running = fireEvent('plugin.running', merge = True)
            log.debug('Still running: %s' % still_running)

            if len(still_running) == 0:
                break

            running = list(set(still_running) - set(self.ignore_restart))
            if len(running) > 0:
                log.info('Waiting on plugins to finish: %s' % running)
            else:
                loop = False

            time.sleep(1)

        if restart:
            self.createFile(self.restartFilePath(), 'This is the most suckiest way to register if CP is restarted. Ever...')

        log.debug('Save to shutdown/restart')

        try:
            request.environ.get('werkzeug.server.shutdown')()
        except RuntimeError:
            pass
        except:
            log.error('Failed shutting down the server: %s' % traceback.format_exc())

        fireEvent('app.after_shutdown', restart = restart)

    def removeRestartFile(self):
        try:
            os.remove(self.restartFilePath())
        except:
            pass

    def restartFilePath(self):
        return os.path.join(Env.get('data_dir'), 'restart')

    def launchBrowser(self):

        if Env.setting('launch_browser'):
            log.info('Launching browser')

            url = self.createBaseUrl()
            try:
                webbrowser.open(url, 2, 1)
            except:
                try:
                    webbrowser.open(url, 1, 1)
                except:
                    log.error('Could not launch a browser.')

    def createBaseUrl(self):
        host = Env.setting('host')
        if host == '0.0.0.0':
            host = 'localhost'
        port = Env.setting('port')

        return '%s:%d%s' % (cleanHost(host).rstrip('/'), int(port), '/' + Env.setting('url_base').lstrip('/') if Env.setting('url_base') else '')

    def createApiUrl(self):
        return '%s/%s' % (self.createBaseUrl(), Env.setting('api_key'))
