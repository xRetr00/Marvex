from .conversation_entities import (
    ENTITY_DIRECTORY,
    ENTITY_FILE,
    ENTITY_WEB_RESULT,
    ConversationEntity,
    ConversationEntityStore,
    resolve_file_reference,
    text_references_prior_file,
)
from .models import (
    SafeSessionHandle,
    SafeConversationProjection,
    SafeSessionProjection,
    TurnLinkageMetadata,
    build_turn_linkage_from_assistant_turn_input,
)
from .registry import BackendSessionCoordinator, CurrentProcessSessionRegistry
from .session_context import SessionContextItem, SessionContextStore

__all__ = [
    "BackendSessionCoordinator",
    "ConversationEntity",
    "ConversationEntityStore",
    "CurrentProcessSessionRegistry",
    "ENTITY_DIRECTORY",
    "ENTITY_FILE",
    "ENTITY_WEB_RESULT",
    "SafeConversationProjection",
    "SafeSessionHandle",
    "SafeSessionProjection",
    "SessionContextItem",
    "SessionContextStore",
    "TurnLinkageMetadata",
    "build_turn_linkage_from_assistant_turn_input",
    "resolve_file_reference",
    "text_references_prior_file",
]
