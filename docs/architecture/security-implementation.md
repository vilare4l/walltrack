# Security Implementation

### Private Key Management

**CRITICAL:** Wallet private keys must NEVER appear in:
- Logs
- UI (Gradio dashboard)
- Git repository
- Database (store encrypted)

**Implementation:**
```python
# src/walltrack/core/security.py
from cryptography.fernet import Fernet
import os

class WalletKeyManager:
    """Encrypt/decrypt wallet private keys"""

    def __init__(self):
        # Encryption key from environment (NOT in code)
        self.cipher = Fernet(os.environ["WALLET_ENCRYPTION_KEY"].encode())

    def encrypt_private_key(self, private_key: str) -> str:
        """Encrypt private key before storing in database"""
        return self.cipher.encrypt(private_key.encode()).decode()

    def decrypt_private_key(self, encrypted_key: str) -> str:
        """Decrypt private key for swap execution"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()

# Usage:
key_manager = WalletKeyManager()
encrypted = key_manager.encrypt_private_key(user_input_private_key)
await db.execute("INSERT INTO config (wallet_private_key_encrypted) VALUES (?)", [encrypted])
```

**Key Storage:**
- Environment variable: `WALLET_ENCRYPTION_KEY` (generate with `Fernet.generate_key()`)
- NEVER commit encryption key to git
- Use `.env` file (added to `.gitignore`)

### Input Validation

**Solana Address Validation:**
```python
import re

def validate_solana_address(address: str) -> bool:
    """Validate Solana address format (base58, 32-44 chars)"""
    pattern = r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"
    return bool(re.match(pattern, address))

# Use in API endpoints:
@app.post("/api/v1/wallets")
async def add_wallet(address: str):
    if not validate_solana_address(address):
        raise HTTPException(400, "Invalid Solana address format")
    # ...
```

### API Security

**Rate Limiting (Future):**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/webhooks/helius")
@limiter.limit("100/minute")  # Helius webhook spam protection
async def helius_webhook(request: Request):
    # Verify HMAC signature
    signature = request.headers.get("X-Helius-Signature")
    if not verify_webhook_signature(await request.body(), signature):
        raise HTTPException(401, "Invalid webhook signature")
    # ...
```

---
