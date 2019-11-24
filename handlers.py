import logging
import traceback
from models import Log, session


class SQLAlchemyHandler(logging.Handler):
    def emit(self, record):
        trace = None
        exc = record.__dict__['exc_info']
        if exc:
            trace = traceback.format_exc()
        log = Log(
                logger=record.__dict__['name'],
                level=record.__dict__['levelname'],
                trace=trace,
                msg=record.__dict__['msg'])
        session.add(log)
        session.commit()
