class TokenVerifier:
    def is_valid(self, token: str) -> bool:
        raise NotImplementedError


class StubTokenVerifier(TokenVerifier):
    def is_valid(self, token: str) -> bool:
        return token == "TEST" or token.startswith("TEST_")


def get_token_verifier() -> TokenVerifier:
    return StubTokenVerifier()
