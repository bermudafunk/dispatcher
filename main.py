from bermudafunk.Base import loop, logger


if __name__ == '__main__':
    logger.debug('Main Start')

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    loop.stop()
