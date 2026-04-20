"""Application state machine primitives."""

from enum import Enum


class StateTransitionError(RuntimeError):
    """Raised when a command is not allowed for the current state."""


class AppState(str, Enum):
    """Top-level runtime states for the application lifecycle."""

    IDLE = "IDLE"
    READY = "READY"
    RUNNING = "RUNNING"
    INJECTION = "INJECTION"
    STOPPED = "STOPPED"
    EMERGENCY = "EMERGENCY"
    FAULT = "FAULT"


class Operation(str, Enum):
    """High-level operations accepted by the controller."""

    START = "START"
    STOP = "STOP"
    MANUAL_INJECTION = "MANUAL_INJECTION"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    RESET_EMERGENCY = "RESET_EMERGENCY"


ALLOWED_TRANSITIONS: dict[AppState, set[AppState]] = {
    AppState.IDLE: {AppState.READY, AppState.RUNNING, AppState.EMERGENCY, AppState.FAULT},
    AppState.READY: {AppState.RUNNING, AppState.STOPPED, AppState.EMERGENCY, AppState.FAULT},
    AppState.RUNNING: {AppState.INJECTION, AppState.STOPPED, AppState.EMERGENCY, AppState.FAULT},
    AppState.INJECTION: {AppState.RUNNING, AppState.STOPPED, AppState.EMERGENCY, AppState.FAULT},
    AppState.STOPPED: {AppState.READY, AppState.RUNNING, AppState.EMERGENCY, AppState.FAULT},
    AppState.EMERGENCY: {AppState.STOPPED},
    AppState.FAULT: {AppState.STOPPED, AppState.EMERGENCY},
}

COMMAND_TRANSITIONS: dict[Operation, dict[AppState, AppState]] = {
    Operation.START: {
        AppState.IDLE: AppState.RUNNING,
        AppState.READY: AppState.RUNNING,
        AppState.STOPPED: AppState.RUNNING,
    },
    Operation.STOP: {
        AppState.IDLE: AppState.STOPPED,
        AppState.READY: AppState.STOPPED,
        AppState.RUNNING: AppState.STOPPED,
        AppState.INJECTION: AppState.STOPPED,
        AppState.FAULT: AppState.STOPPED,
    },
    Operation.MANUAL_INJECTION: {
        AppState.RUNNING: AppState.INJECTION,
    },
    Operation.EMERGENCY_STOP: {
        AppState.IDLE: AppState.EMERGENCY,
        AppState.READY: AppState.EMERGENCY,
        AppState.RUNNING: AppState.EMERGENCY,
        AppState.INJECTION: AppState.EMERGENCY,
        AppState.STOPPED: AppState.EMERGENCY,
        AppState.EMERGENCY: AppState.EMERGENCY,
        AppState.FAULT: AppState.EMERGENCY,
    },
    Operation.RESET_EMERGENCY: {
        AppState.EMERGENCY: AppState.STOPPED,
    },
}

EMERGENCY_FORBIDDEN_OPERATIONS: set[Operation] = {
    Operation.START,
    Operation.STOP,
    Operation.MANUAL_INJECTION,
}


class StateMachine:
    """Validate application state transitions and command availability."""

    def __init__(self, state: AppState = AppState.IDLE) -> None:
        self.state = state

    def transition_to(self, next_state: AppState) -> AppState:
        """Move to ``next_state`` if the transition is declared as safe."""
        if next_state == self.state:
            return self.state

        if next_state not in ALLOWED_TRANSITIONS[self.state]:
            raise StateTransitionError(
                f"Transition {self.state.value} -> {next_state.value} is not allowed"
            )

        self.state = next_state
        return self.state

    def apply(self, operation: Operation) -> AppState:
        """Apply a command operation and return the new state."""
        self.assert_operation_allowed(operation)
        next_state = COMMAND_TRANSITIONS.get(operation, {}).get(self.state)
        if next_state is None:
            raise StateTransitionError(
                f"Operation {operation.value} is not allowed in state {self.state.value}"
            )
        return self.transition_to(next_state)

    def assert_operation_allowed(self, operation: Operation) -> None:
        """Reject unsafe commands in EMERGENCY before side effects happen."""
        if self.state == AppState.EMERGENCY and operation in EMERGENCY_FORBIDDEN_OPERATIONS:
            raise StateTransitionError(
                f"Operation {operation.value} is forbidden in state {AppState.EMERGENCY.value}"
            )
