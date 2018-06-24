from bermudafunk import base
from bermudafunk.base import systemd

if __name__ == '__main__':
    base.logger.debug('Main Start')

    try:
        systemd.setup()
    except:
        pass

    base.run_loop()
