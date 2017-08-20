from django.apps import AppConfig


class Ico(AppConfig):
    name = 'ico'

    def ready(self):
        # Preferred method for instanciating signal not defined
        # in the models submodule
        import ico.signals
