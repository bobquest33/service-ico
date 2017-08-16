from enumfields import Enum

class WebhookEvent(Enum):
    USER_CREATE = 'user.create'
    USER_UPDATE = 'user.update'
    USER_DELETE = 'user.delete'
    USER_PASSWORD_RESET = 'user.password.reset'
    USER_EMAIL_VERIFY = 'user.email.verify'
    USER_MOBILE_VERIFY = 'user.mobile.verify'
    TRANSACTION_CREATE = 'transaction.create'
    TRANSACTION_UPDATE = 'transaction.update'
    TRANSACTION_DELETE = 'transaction.delete'
    TRANSACTION_INITIATE = 'transaction.initiate'
    TRANSACTION_EXECUTE = 'transaction.execute'
