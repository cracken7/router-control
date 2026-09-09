# throwaway probe — sanitized (credentials moved to config.json); see zte_client.py
from zte_client import ZteClient

c = ZteClient()
print("LOGIN:", c.login())
