import datetime
from pathlib import Path
import pandas as pd
import pytest
from unittest.mock import Mock, patch, PropertyMock
from decimal import Decimal
from app.calculator import Calculator
from app.calculator_repl import calculator_repl
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError, ValidationError
from app.history import LoggingObserver, AutoSaveObserver
from app.operations import OperationFactory
from app.calculation import Calculation
from app.calculator_memento import CalculatorMemento

# Fixture to initialize Calculator with a temporary directory for file paths
@pytest.fixture
def calculator(tmp_path):
    temp_path = tmp_path
    config = CalculatorConfig(base_dir=temp_path)

    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file, \
         patch.object(CalculatorConfig, 'history_dir', new_callable=PropertyMock) as mock_history_dir, \
         patch.object(CalculatorConfig, 'history_file', new_callable=PropertyMock) as mock_history_file:

        mock_log_dir.return_value = temp_path / "logs"
        mock_log_file.return_value = temp_path / "logs" / "calculator.log"
        mock_history_dir.return_value = temp_path / "history"
        mock_history_file.return_value = temp_path / "history" / "calculator_history.csv"

        yield Calculator(config=config)
# Test Calculator Initialization

def test_calculator_initialization(calculator):
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []
    assert calculator.operation_strategy is None

# Test Logging Setup

@patch('app.calculator.logging.info')
def test_logging_setup(logging_info_mock):
    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file:
        mock_log_dir.return_value = Path('/tmp/logs')
        mock_log_file.return_value = Path('/tmp/logs/calculator.log')
        
        # Instantiate calculator to trigger logging
        calculator = Calculator(CalculatorConfig())
        logging_info_mock.assert_any_call("Calculator initialized with configuration")

# Test Adding and Removing Observers

def test_add_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    assert observer in calculator.observers

def test_remove_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    calculator.remove_observer(observer)
    assert observer not in calculator.observers

# Test Setting Operations

def test_set_operation(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    assert calculator.operation_strategy == operation

# Test Performing Operations

def test_perform_operation_addition(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    result = calculator.perform_operation(2, 3)
    assert result == Decimal('5')

def test_perform_operation_validation_error(calculator):
    calculator.set_operation(OperationFactory.create_operation('add'))
    with pytest.raises(ValidationError):
        calculator.perform_operation('invalid', 3)

def test_perform_operation_operation_error(calculator):
    with pytest.raises(OperationError, match="No operation set"):
        calculator.perform_operation(2, 3)

# Test Undo/Redo Functionality

def test_undo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    assert calculator.history == []

def test_redo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    calculator.redo()
    assert len(calculator.history) == 1

# Test History Management

@patch('app.calculator.pd.DataFrame.to_csv')
def test_save_history(mock_to_csv, calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.save_history()
    mock_to_csv.assert_called_once()

@patch('app.calculator.pd.read_csv')
@patch('app.calculator.Path.exists', return_value=True)
def test_load_history(mock_exists, mock_read_csv, calculator):
    # Mock CSV data to match the expected format in from_dict
    mock_read_csv.return_value = pd.DataFrame({
        'operation': ['Addition'],
        'operand1': ['2'],
        'operand2': ['3'],
        'result': ['5'],
        'timestamp': [datetime.datetime.now().isoformat()]
    })
    
    # Test the load_history functionality
    try:
        calculator.load_history()
        # Verify history length after loading
        assert len(calculator.history) == 1
        # Verify the loaded values
        assert calculator.history[0].operation == "Addition"
        assert calculator.history[0].operand1 == Decimal("2")
        assert calculator.history[0].operand2 == Decimal("3")
        assert calculator.history[0].result == Decimal("5")
    except OperationError:
        pytest.fail("Loading history failed due to OperationError")
        
            
# Test Clearing History

def test_clear_history(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.clear_history()
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []

# Test REPL Commands (using patches for input/output handling)

@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()
        mock_save_history.assert_called_once()
        mock_print.assert_any_call("History saved successfully.")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_help(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nAvailable commands:")

@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_addition(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 5")

# Additional tests for 100% coverage

def test_history_max_size(calculator):
    """Test that history is limited to max_history_size."""
    calculator.config.max_history_size = 2

    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)

    calculator.perform_operation(1, 2)
    calculator.perform_operation(2, 3)
    calculator.perform_operation(3, 4)

    assert len(calculator.history) == 2
    assert calculator.history[0].operand1 == Decimal("2")
    assert calculator.history[1].operand1 == Decimal("3")


def test_get_history_dataframe(calculator):
    """Test converting calculation history to a DataFrame."""
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)

    df = calculator.get_history_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert "operation" in df.columns
    assert "operand1" in df.columns
    assert "operand2" in df.columns
    assert "result" in df.columns
    assert "timestamp" in df.columns


def test_show_history(calculator):
    """Test formatted history output."""
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)

    history = calculator.show_history()

    assert len(history) == 1
    assert "Addition" in history[0]
    assert "2" in history[0]
    assert "3" in history[0]
    assert "5" in history[0]


def test_undo_when_empty(calculator):
    """Test undo when there is nothing to undo."""
    assert calculator.undo() is False


def test_redo_when_empty(calculator):
    """Test redo when there is nothing to redo."""
    assert calculator.redo() is False


def test_save_empty_history(calculator):
    """Test saving an empty history."""
    calculator.save_history()

    assert calculator.config.history_file.exists()


def test_load_empty_history(calculator):
    """Test loading an empty history file."""
    calculator.config.history_file.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        columns=[
            'operation',
            'operand1',
            'operand2',
            'result',
            'timestamp'
        ]
    ).to_csv(calculator.config.history_file, index=False)

    calculator.load_history()

    assert calculator.history == []


def test_load_history_file_not_found(calculator):
    """Test loading when the history file does not exist."""
    assert not calculator.config.history_file.exists()

    calculator.load_history()

    assert calculator.history == []

@patch('builtins.input', side_effect=['subtract', '5', '2', 'exit'])
@patch('builtins.print')
def test_calculator_repl_subtraction(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 3")


@patch('builtins.input', side_effect=['multiply', '4', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_multiplication(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 12")


@patch('builtins.input', side_effect=['divide', '10', '2', 'exit'])
@patch('builtins.print')
def test_calculator_repl_division(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 5")


@patch('builtins.input', side_effect=['history', 'exit'])
@patch('builtins.print')
def test_calculator_repl_history(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nCalculation History:")


@patch('builtins.input', side_effect=['clear', 'exit'])
@patch('builtins.print')
def test_calculator_repl_clear(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("History cleared")


@patch('builtins.input', side_effect=['undo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_undo(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Nothing to undo")


@patch('builtins.input', side_effect=['redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_redo(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Nothing to redo")

def test_calculator_perform_operation_unexpected_error(calculator):
    """Test that unexpected operation errors are converted to OperationError."""
    mock_operation = Mock()
    mock_operation.execute.side_effect = Exception("Test error")

    calculator.set_operation(mock_operation)

    with pytest.raises(OperationError, match="Operation failed: Test error"):
        calculator.perform_operation(2, 3)

def test_calculator_save_history_error(calculator):
    """Test save_history handles file errors."""
    with patch("app.calculator.Path.mkdir", side_effect=OSError("Test save error")):
        with pytest.raises(OperationError, match="Failed to save history"):
            calculator.save_history()


def test_calculator_load_history_error(calculator):
    """Test load_history handles file errors."""
    with patch("app.calculator.Path.exists", side_effect=OSError("Test load error")):
        with pytest.raises(OperationError, match="Failed to load history"):
            calculator.load_history()

def test_calculator_logging_error():
    """Test logging setup handles an exception."""
    config = CalculatorConfig()

    with patch("app.calculator.os.makedirs", side_effect=OSError("Logging error")):
        with pytest.raises(OSError, match="Logging error"):
            Calculator(config)


def test_calculator_without_config():
    """Test calculator creates default configuration when none is provided."""
    with patch("app.calculator.CalculatorConfig") as mock_config_class:
        mock_config = Mock()
        mock_config.log_dir = Path("logs")
        mock_config.log_file = Path("logs/calculator.log")
        mock_config.history_dir = Path("history")
        mock_config.history_file = Path("history/calculator_history.csv")
        mock_config.max_history_size = 100
        mock_config_class.return_value = mock_config

        with patch("app.calculator.os.makedirs"):
            with patch.object(Calculator, "_setup_logging"):
                with patch.object(Calculator, "_setup_directories"):
                    with patch.object(Calculator, "load_history"):
                        calculator = Calculator()

        assert calculator.config == mock_config

def test_calculator_without_config():
    """Test calculator creates default configuration."""
    with patch("app.calculator.CalculatorConfig") as mock_config_class:
        mock_config = Mock()
        mock_config.log_dir = Path("logs")
        mock_config.log_file = Path("logs/calculator.log")
        mock_config.history_dir = Path("history")
        mock_config.history_file = Path("history/calculator_history.csv")
        mock_config.max_history_size = 100

        mock_config_class.return_value = mock_config

        with patch("app.calculator.os.makedirs"):
            with patch.object(Calculator, "_setup_logging"):
                with patch.object(Calculator, "_setup_directories"):
                    with patch.object(Calculator, "load_history"):
                        calculator = Calculator()

        assert calculator.config == mock_config


def test_calculator_logging_error(calculator):
    """Test logging setup handles an exception."""
    with patch(
        "app.calculator.os.makedirs",
        side_effect=OSError("Logging error")
    ):
        with pytest.raises(OSError, match="Logging error"):
            calculator._setup_logging()

def test_calculator_memento_to_dict_and_from_dict():
    """Test converting a calculator memento to and from a dictionary."""
    calculation = Calculation(
        operation="Addition",
        operand1=2,
        operand2=3
    )

    memento = CalculatorMemento(history=[calculation])

    data = memento.to_dict()

    restored = CalculatorMemento.from_dict(data)

    assert len(restored.history) == 1
    assert restored.history[0].operand1 == 2
    assert restored.history[0].operand2 == 3

def test_calculator_uses_default_config():
    """Test Calculator creates a default config when none is provided."""
    mock_config = Mock()
    mock_config.log_dir = Path("logs")
    mock_config.log_file = Path("logs/calculator.log")
    mock_config.history_dir = Path("history")
    mock_config.history_file = Path("history/calculator_history.csv")
    mock_config.max_history_size = 100

    with patch(
        "app.calculator.CalculatorConfig",
        return_value=mock_config
    ):
        with patch("app.calculator.os.makedirs"):
            with patch.object(Calculator, "_setup_logging"):
                with patch.object(Calculator, "_setup_directories"):
                    with patch.object(Calculator, "load_history"):
                        calculator = Calculator()

    assert calculator.config == mock_config
def test_calculation_unknown_operation():
    """Test that an unknown operation raises OperationError."""
    with pytest.raises(OperationError, match="Unknown operation"):
        Calculation(
            operation="Unknown",
            operand1=Decimal("2"),
            operand2=Decimal("3")
        )


def test_calculation_invalid_data():
    """Test invalid calculation data raises OperationError."""
    data = {
        "operation": "Addition",
        "operand1": "invalid",
        "operand2": "3",
        "result": "6",
        "timestamp": datetime.datetime.now().isoformat()
    }

    with pytest.raises(OperationError, match="Invalid calculation data"):
        Calculation.from_dict(data)


def test_calculation_not_equal_to_other_type():
    """Test comparison with a non-Calculation object."""
    calculation = Calculation(
        operation="Addition",
        operand1=Decimal("2"),
        operand2=Decimal("3")
    )

    assert calculation.__eq__("not a calculation") is NotImplemented


def test_calculation_format_result():
    """Test formatting a calculation result."""
    calculation = Calculation(
        operation="Addition",
        operand1=Decimal("2"),
        operand2=Decimal("3")
    )

    assert calculation.format_result() == "5"


@patch("builtins.input", side_effect=["add", "2", "3", "exit"])
@patch("builtins.print")
def test_calculator_repl_add(mock_print, mock_input):
    """Test addition through the calculator REPL."""
    calculator_repl()

    mock_print.assert_any_call("\nResult: 5")

@patch("builtins.input", side_effect=["invalid", "exit"])
@patch("builtins.print")
def test_calculator_repl_invalid_command(mock_print, mock_input):
    """Test an invalid command in the REPL."""
    calculator_repl()

    assert mock_print.called

@patch("builtins.input", side_effect=["add", "2", "abc", "exit"])
@patch("builtins.print")
def test_calculator_repl_invalid_second_number(mock_print, mock_input):
    """Test invalid input for the second number."""
    calculator_repl()

    assert mock_print.called