import ast
import cmath
import datetime
import json
import math
import operator
import random
import secrets
import statistics
import sys
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Try importing optional libraries for extended functionality
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import sympy

    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# =====================================================================
# Input Helpers & Utilities
# =====================================================================
def get_float(prompt: str) -> float:
    """Prompt user for a valid floating-point number."""
    while True:
        try:
            val = input(prompt).strip()
            return float(val)
        except ValueError:
            print("Error: Invalid input. Please enter a valid number.")


def get_int(prompt: str, min_val: Optional[int] = None) -> int:
    """Prompt user for a valid integer, optionally enforcing a minimum value."""
    while True:
        try:
            val = input(prompt).strip()
            res = int(val)
            if min_val is not None and res < min_val:
                print(f"Error: Value must be at least {min_val}.")
                continue
            return res
        except ValueError:
            print("Error: Invalid input. Please enter a valid integer.")


def get_float_list(prompt: str) -> List[float]:
    """Prompt user for a list of numbers separated by spaces or commas."""
    while True:
        line = input(prompt).strip().replace(",", " ")
        if not line:
            print("Error: Input cannot be empty.")
            continue
        try:
            return [float(x) for x in line.split()]
        except ValueError:
            print("Error: All entries must be valid numeric values.")


def get_complex(prompt: str) -> complex:
    """Prompt user for a complex number (e.g., '3+4j', '5', or '2j')."""
    while True:
        val = input(prompt).strip().replace("i", "j")
        try:
            return complex(val)
        except ValueError:
            print("Error: Invalid complex number format. Use format 'a+bj' (e.g., 3+4j).")


# =====================================================================
# Safe AST Expression Parser
# =====================================================================
class SafeMathEvaluator(ast.NodeVisitor):
    """Safely evaluates mathematical expressions without using unsafe eval()."""

    def __init__(self, variables: Optional[Dict[str, float]] = None):
        self.variables = variables or {}
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.BitXor: operator.pow,  # Allow 3^2 as exponentiation
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        self.functions = {
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            "sinh": math.sinh,
            "cosh": math.cosh,
            "tanh": math.tanh,
            "asinh": math.asinh,
            "acosh": math.acosh,
            "atanh": math.atanh,
            "sqrt": math.sqrt,
            "log": math.log,
            "log10": math.log10,
            "ln": math.log,
            "exp": math.exp,
            "abs": abs,
            "ceil": math.ceil,
            "floor": math.floor,
            "factorial": math.factorial,
            "fact": math.factorial,
            "gcd": math.gcd,
            "lcm": math.lcm,
            "comb": math.comb,
            "perm": math.perm,
            "radians": math.radians,
            "degrees": math.degrees,
            "rad": math.radians,
            "deg": math.degrees,
        }
        self.constants = {
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
            "inf": math.inf,
        }

    def evaluate(self, expr_str: str) -> float:
        clean_expr = expr_str.strip().replace("^", "**")
        if not clean_expr:
            raise ValueError("Expression is empty.")

        try:
            node = ast.parse(clean_expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Syntax error in expression: {e}")

        return self.visit(node.body)

    def visit_Num(self, node: ast.Num) -> float:
        return float(node.n)

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    def visit_Name(self, node: ast.Name) -> float:
        name = node.id
        if name in self.variables:
            return self.variables[name]
        if name in self.constants:
            return self.constants[name]
        raise ValueError(f"Unknown variable or constant: '{name}'")

    def visit_BinOp(self, node: ast.BinOp) -> float:
        op_type = type(node.op)
        if op_type not in self.operators:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self.operators[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        op_type = type(node.op)
        if op_type not in self.operators:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = self.visit(node.operand)
        return self.operators[op_type](operand)

    def visit_Call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are supported.")
        func_name = node.func.id
        if func_name not in self.functions:
            raise ValueError(f"Unsupported function: '{func_name}'")
        args = [self.visit(arg) for arg in node.args]
        if func_name in ("factorial", "fact", "gcd", "lcm", "comb", "perm"):
            args = [int(a) if isinstance(a, (int, float)) and float(a).is_integer() else a for a in args]
        return float(self.functions[func_name](*args))

    def generic_visit(self, node: ast.AST):
        raise ValueError(f"Unsupported expression syntax: {type(node).__name__}")


# =====================================================================
# Main Comprehensive Calculator Class
# =====================================================================
class AdvancedCalculator:
    def __init__(self):
        self.angle_unit = "degrees"  # 'degrees' or 'radians'
        self.history: List[Tuple[str, Any]] = []

    def run(self):
        while True:
            self._print_header("ADVANCED MATHEMATICAL CALCULATOR")
            print(" 1. Basic Arithmetic (+, -, *, /)")
            print(" 2. Scientific & Hyperbolic Functions")
            print(" 3. Programmer & Bitwise Calculations (Bases & Bitwise)")
            print(" 4. Complex Number Arithmetic")
            print(" 5. Safe Expression Evaluator (e.g., (5+3)*2^4)")
            print(" 6. Matrix & Linear Algebra Operations")
            print(" 7. Calculus & Equation Solving")
            print(" 8. Geometry & Mensuration (2D/3D Area & Volume)")
            print(" 9. Function Plotting & ASCII Charts")
            print("10. Date & Time Arithmetic")
            print("11. Unit & Currency Converters")
            print("12. Financial Calculations (Interest, Mortgage, NPV)")
            print("13. Statistical Calculations & Regression")
            print("14. Probability, Dice & Randomness")
            print("15. Health & Fitness Metrics (BMI, BMR, TDEE)")
            print("16. History Memory & Settings")
            print("17. Exit")
            print("=" * 60)

            choice = input("Select an option (1-17): ").strip()
            if choice == "1":
                self.basic_arithmetic_menu()
            elif choice == "2":
                self.scientific_menu()
            elif choice == "3":
                self.programmer_menu()
            elif choice == "4":
                self.complex_menu()
            elif choice == "5":
                self.expression_evaluator_menu()
            elif choice == "6":
                self.matrix_menu()
            elif choice == "7":
                self.calculus_menu()
            elif choice == "8":
                self.geometry_menu()
            elif choice == "9":
                self.plotting_menu()
            elif choice == "10":
                self.datetime_menu()
            elif choice == "11":
                self.converters_menu()
            elif choice == "12":
                self.financial_menu()
            elif choice == "13":
                self.statistics_menu()
            elif choice == "14":
                self.probability_menu()
            elif choice == "15":
                self.fitness_menu()
            elif choice == "16":
                self.history_settings_menu()
            elif choice == "17":
                print("\nThank you for using Advanced Calculator. Goodbye!")
                sys.exit(0)
            else:
                print("Invalid choice. Please select between 1 and 17.")
                self._pause()

    def _print_header(self, title: str):
        print("\n" + "=" * 60)
        print(f"{title.center(60)}")
        print("=" * 60)

    def _pause(self):
        input("\nPress Enter to continue...")

    def _record_history(self, expr: str, result: Any):
        self.history.append((expr, result))
        if len(self.history) > 100:
            self.history.pop(0)

    @staticmethod
    def _format_number(val: float) -> str:
        if math.isnan(val):
            return "NaN"
        if math.isinf(val):
            return "Inf"
        if abs(val - round(val)) < 1e-11:
            return str(int(round(val)))
        return f"{val:.6g}"

    # =================================================================
    # 1. Basic Arithmetic
    # =================================================================
    def basic_arithmetic_menu(self):
        while True:
            self._print_header("BASIC ARITHMETIC")
            print("1. Addition (+)")
            print("2. Subtraction (-)")
            print("3. Multiplication (*)")
            print("4. Division (/)")
            print("5. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-5): ").strip()
            if choice == "5":
                break
            if choice not in ("1", "2", "3", "4"):
                print("Invalid choice.")
                self._pause()
                continue

            num1 = get_float("Enter first number: ")
            num2 = get_float("Enter second number: ")

            if choice == "1":
                res = num1 + num2
                expr = f"{num1} + {num2}"
            elif choice == "2":
                res = num1 - num2
                expr = f"{num1} - {num2}"
            elif choice == "3":
                res = num1 * num2
                expr = f"{num1} * {num2}"
            elif choice == "4":
                if num2 == 0:
                    print("\nError: Division by zero is undefined.")
                    self._pause()
                    continue
                res = num1 / num2
                expr = f"{num1} / {num2}"

            formatted = self._format_number(res)
            print(f"\nResult: {expr} = {formatted}")
            self._record_history(expr, res)
            self._pause()

    # =================================================================
    # 2. Scientific & Hyperbolic Functions
    # =================================================================
    def scientific_menu(self):
        while True:
            self._print_header("SCIENTIFIC & HYPERBOLIC FUNCTIONS")
            print(" 1. Exponentiation (x^y)")
            print(" 2. Square Root (√x)")
            print(" 3. Modulus (x % y)")
            print(" 4. Logarithms (ln, log10, log_b)")
            print(" 5. Factorial (n!)")
            print(" 6. Permutations (nPr) & Combinations (nCr)")
            print(f" 7. Trigonometry (sin, cos, tan) [{self.angle_unit.title()}]")
            print(f" 8. Inverse Trigonometry (asin, acos, atan) [{self.angle_unit.title()}]")
            print(" 9. Hyperbolic Functions (sinh, cosh, tanh)")
            print("10. GCD & LCM")
            print("11. Degree / Radian Conversions")
            print("12. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-12): ").strip()
            if choice == "12":
                break

            try:
                if choice == "1":
                    base = get_float("Enter base (x): ")
                    exp = get_float("Enter exponent (y): ")
                    res = math.pow(base, exp)
                    expr = f"{base}^{exp}"
                    print(f"\nResult: {expr} = {self._format_number(res)}")
                    self._record_history(expr, res)

                elif choice == "2":
                    val = get_float("Enter number (x): ")
                    if val < 0:
                        print("\nError: Square root of a negative number is undefined in real numbers.")
                    else:
                        res = math.sqrt(val)
                        expr = f"√({val})"
                        print(f"\nResult: {expr} = {self._format_number(res)}")
                        self._record_history(expr, res)

                elif choice == "3":
                    num1 = get_float("Enter dividend (x): ")
                    num2 = get_float("Enter divisor (y): ")
                    if num2 == 0:
                        print("\nError: Modulus by zero is undefined.")
                    else:
                        res = num1 % num2
                        expr = f"{num1} % {num2}"
                        print(f"\nResult: {expr} = {self._format_number(res)}")
                        self._record_history(expr, res)

                elif choice == "4":
                    print("\n--- Logarithms ---")
                    print("1. Natural Log (ln x)")
                    print("2. Base-10 Log (log10 x)")
                    print("3. Base-b Log (log_b x)")
                    log_choice = input("Select option (1-3): ").strip()
                    val = get_float("Enter x (must be > 0): ")
                    if val <= 0:
                        print("\nError: Logarithm undefined for x <= 0.")
                    elif log_choice == "1":
                        res = math.log(val)
                        expr = f"ln({val})"
                        print(f"\nResult: {expr} = {self._format_number(res)}")
                        self._record_history(expr, res)
                    elif log_choice == "2":
                        res = math.log10(val)
                        expr = f"log10({val})"
                        print(f"\nResult: {expr} = {self._format_number(res)}")
                        self._record_history(expr, res)
                    elif log_choice == "3":
                        base = get_float("Enter base (b > 0, b != 1): ")
                        if base <= 0 or base == 1:
                            print("\nError: Base must be > 0 and != 1.")
                        else:
                            res = math.log(val, base)
                            expr = f"log_{base}({val})"
                            print(f"\nResult: {expr} = {self._format_number(res)}")
                            self._record_history(expr, res)

                elif choice == "5":
                    val = get_float("Enter integer (n >= 0): ")
                    if val < 0 or not val.is_integer():
                        print("\nError: Factorial requires a non-negative integer.")
                    else:
                        n = int(val)
                        res = math.factorial(n)
                        expr = f"{n}!"
                        print(f"\nResult: {expr} = {res}")
                        self._record_history(expr, res)

                elif choice == "6":
                    n = get_int("Enter n (total items): ", min_val=0)
                    r = get_int("Enter r (selected items): ", min_val=0)
                    if r > n:
                        print("\nError: r cannot be greater than n.")
                    else:
                        p_res = math.perm(n, r)
                        c_res = math.comb(n, r)
                        print(f"\nPermutations  {n}P{r} = {p_res}")
                        print(f"Combinations  {n}C{r} = {c_res}")
                        self._record_history(f"{n}P{r}", p_res)
                        self._record_history(f"{n}C{r}", c_res)

                elif choice == "7":
                    angle = get_float("Enter angle: ")
                    rad = math.radians(angle) if self.angle_unit == "degrees" else angle
                    sin_val = math.sin(rad)
                    cos_val = math.cos(rad)
                    tan_val = "Undefined (asymptote)" if abs(cos_val) < 1e-15 else self._format_number(math.tan(rad))
                    print(f"\nsin({angle} {self.angle_unit}) = {self._format_number(sin_val)}")
                    print(f"cos({angle} {self.angle_unit}) = {self._format_number(cos_val)}")
                    print(f"tan({angle} {self.angle_unit}) = {tan_val}")
                    self._record_history(f"sin({angle})", sin_val)

                elif choice == "8":
                    val = get_float("Enter value (-1 to 1 for asin/acos): ")
                    try:
                        asin_rad = math.asin(val)
                        acos_rad = math.acos(val)
                        atan_rad = math.atan(val)
                        if self.angle_unit == "degrees":
                            print(f"\nasin({val}) = {self._format_number(math.degrees(asin_rad))}°")
                            print(f"acos({val}) = {self._format_number(math.degrees(acos_rad))}°")
                            print(f"atan({val}) = {self._format_number(math.degrees(atan_rad))}°")
                        else:
                            print(f"\nasin({val}) = {self._format_number(asin_rad)} rad")
                            print(f"acos({val}) = {self._format_number(acos_rad)} rad")
                            print(f"atan({val}) = {self._format_number(atan_rad)} rad")
                        self._record_history(f"asin({val})", asin_rad)
                    except ValueError:
                        print("\nError: Domain error. Inputs for asin and acos must be between -1 and 1.")

                elif choice == "9":
                    val = get_float("Enter x: ")
                    sinh_v = math.sinh(val)
                    cosh_v = math.cosh(val)
                    tanh_v = math.tanh(val)
                    print(f"\nsinh({val}) = {self._format_number(sinh_v)}")
                    print(f"cosh({val}) = {self._format_number(cosh_v)}")
                    print(f"tanh({val}) = {self._format_number(tanh_v)}")
                    self._record_history(f"sinh({val})", sinh_v)

                elif choice == "10":
                    a = get_int("Enter first integer: ")
                    b = get_int("Enter second integer: ")
                    gcd_v = math.gcd(a, b)
                    lcm_v = math.lcm(a, b)
                    print(f"\nGCD({a}, {b}) = {gcd_v}")
                    print(f"LCM({a}, {b}) = {lcm_v}")
                    self._record_history(f"gcd({a},{b})", gcd_v)
                    self._record_history(f"lcm({a},{b})", lcm_v)

                elif choice == "11":
                    val = get_float("Enter angle value: ")
                    print(f"\n{val} degrees = {self._format_number(math.radians(val))} radians")
                    print(f"{val} radians = {self._format_number(math.degrees(val))} degrees")

            except OverflowError:
                print("\nError: Numeric result overflowed maximum float bounds.")
            except Exception as e:
                print(f"\nError: {e}")

            self._pause()

    # =================================================================
    # 3. Programmer & Bitwise Calculations
    # =================================================================
    def programmer_menu(self):
        while True:
            self._print_header("PROGRAMMER & BITWISE CALCULATIONS")
            print("1. Instant Base Conversion (Dec, Bin, Hex, Oct)")
            print("2. Bitwise AND (&)")
            print("3. Bitwise OR (|)")
            print("4. Bitwise XOR (^)")
            print("5. Bitwise NOT (~)")
            print("6. Left Shift (<<)")
            print("7. Right Shift (>>)")
            print("8. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-8): ").strip()
            if choice == "8":
                break

            if choice not in ("1", "2", "3", "4", "5", "6", "7"):
                print("Invalid choice.")
                self._pause()
                continue

            try:
                if choice == "1":
                    inp = input("Enter integer (prefix with 0b for binary, 0x for hex, 0o for octal): ").strip()
                    val = int(inp, 0)
                    self._print_base_conversions(val)

                elif choice in ("2", "3", "4"):
                    a = int(input("Enter first integer (A): ").strip(), 0)
                    b = int(input("Enter second integer (B): ").strip(), 0)
                    if choice == "2":
                        res = a & b
                        op = "&"
                    elif choice == "3":
                        res = a | b
                        op = "|"
                    else:
                        res = a ^ b
                        op = "^"

                    print(f"\nResult: {a} {op} {b} = {res}")
                    self._print_base_conversions(res)

                elif choice == "5":
                    a = int(input("Enter integer (A): ").strip(), 0)
                    res = ~a
                    print(f"\nResult: ~{a} = {res}")
                    self._print_base_conversions(res)

                elif choice in ("6", "7"):
                    a = int(input("Enter integer (A): ").strip(), 0)
                    shift = get_int("Enter shift amount (bits): ", min_val=0)
                    if choice == "6":
                        res = a << shift
                        op = "<<"
                    else:
                        res = a >> shift
                        op = ">>"

                    print(f"\nResult: {a} {op} {shift} = {res}")
                    self._print_base_conversions(res)

            except ValueError:
                print("Error: Invalid numeric input format.")

            self._pause()

    def _print_base_conversions(self, val: int):
        print("\n--- Base Representation ---")
        print(f"Decimal:     {val}")
        print(f"Hexadecimal: {hex(val).upper()}")
        print(f"Octal:       {oct(val)}")
        if val >= 0:
            bin_str = bin(val)[2:]
            # Format in 4-bit blocks
            padded_len = math.ceil(len(bin_str) / 4) * 4
            bin_padded = bin_str.zfill(max(8, padded_len))
            formatted_bin = " ".join(bin_padded[i:i+4] for i in range(0, len(bin_padded), 4))
            print(f"Binary:      0b {formatted_bin}")
        else:
            print(f"Binary:      {bin(val)}")

    # =================================================================
    # 4. Complex Number Arithmetic
    # =================================================================
    def complex_menu(self):
        while True:
            self._print_header("COMPLEX NUMBER ARITHMETIC")
            print("1. Addition (z1 + z2)")
            print("2. Subtraction (z1 - z2)")
            print("3. Multiplication (z1 * z2)")
            print("4. Division (z1 / z2)")
            print("5. Complex Properties (Magnitude, Phase Angle, Conjugate)")
            print("6. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-6): ").strip()
            if choice == "6":
                break

            if choice not in ("1", "2", "3", "4", "5"):
                print("Invalid choice.")
                self._pause()
                continue

            try:
                if choice in ("1", "2", "3", "4"):
                    z1 = get_complex("Enter z1 (e.g. 3+4j): ")
                    z2 = get_complex("Enter z2 (e.g. 1-2j): ")
                    if choice == "1":
                        res = z1 + z2
                        expr = f"({z1}) + ({z2})"
                    elif choice == "2":
                        res = z1 - z2
                        expr = f"({z1}) - ({z2})"
                    elif choice == "3":
                        res = z1 * z2
                        expr = f"({z1}) * ({z2})"
                    elif choice == "4":
                        if z2 == 0:
                            print("\nError: Complex division by zero.")
                            self._pause()
                            continue
                        res = z1 / z2
                        expr = f"({z1}) / ({z2})"

                    print(f"\nResult: {expr} = {res}")
                    self._record_history(expr, res)

                elif choice == "5":
                    z = get_complex("Enter complex number z (e.g. 3+4j): ")
                    mag = abs(z)
                    phase_rad = cmath.phase(z)
                    phase_deg = math.degrees(phase_rad)
                    conj = z.conjugate()
                    print(f"\n--- Properties of z = {z} ---")
                    print(f"Real Part (Re):      {z.real}")
                    print(f"Imaginary Part (Im): {z.imag}")
                    print(f"Magnitude |z| (r):   {self._format_number(mag)}")
                    print(f"Phase Angle (θ):     {self._format_number(phase_deg)}° ({self._format_number(phase_rad)} rad)")
                    print(f"Complex Conjugate:   {conj}")
                    print(f"Polar Form:          {self._format_number(mag)} * e^({self._format_number(phase_deg)}° i)")

            except Exception as e:
                print(f"\nError: {e}")

            self._pause()

    # =================================================================
    # 5. Safe Expression Evaluator
    # =================================================================
    def expression_evaluator_menu(self):
        self._print_header("EXPRESSION EVALUATOR")
        print("Enter full mathematical expressions directly.")
        print("Supported: +, -, *, /, ^ (or **), %, functions (sin, cos, sqrt, log, ln, factorial, etc.)")
        print("Variables: 'ans' (last result), 'pi', 'e'")
        print("Type 'back' to return to menu.\n")

        last_res = self.history[-1][1] if (self.history and isinstance(self.history[-1][1], (int, float))) else 0.0
        evaluator = SafeMathEvaluator(variables={"ans": last_res})

        while True:
            expr_str = input("calc> ").strip()
            if expr_str.lower() in ("back", "exit", "quit"):
                break
            if not expr_str:
                continue

            try:
                if self.history and isinstance(self.history[-1][1], (int, float)):
                    evaluator.variables["ans"] = float(self.history[-1][1])

                res = evaluator.evaluate(expr_str)
                formatted = self._format_number(res)
                print(f"= {formatted}\n")
                self._record_history(expr_str, res)
            except Exception as e:
                print(f"Error: {e}\n")

    # =================================================================
    # 6. Matrix & Linear Algebra Operations
    # =================================================================
    def matrix_menu(self):
        while True:
            self._print_header("MATRIX & LINEAR ALGEBRA OPERATIONS")
            print("1. Matrix Addition (A + B)")
            print("2. Matrix Subtraction (A - B)")
            print("3. Matrix Multiplication (A * B)")
            print("4. Matrix Transposition (A^T)")
            print("5. Scalar Multiplication (c * A)")
            print("6. Matrix Determinant det(A)")
            print("7. Matrix Inversion (A^-1)")
            print("8. Eigenvalues & Eigenvectors")
            print("9. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-9): ").strip()
            if choice == "9":
                break

            if choice not in ("1", "2", "3", "4", "5", "6", "7", "8"):
                print("Invalid choice.")
                self._pause()
                continue

            try:
                if choice == "1":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    print("\n--- Matrix B ---")
                    B = self._input_matrix()
                    if len(A) != len(B) or len(A[0]) != len(B[0]):
                        print(f"\nError: Dimension mismatch! A is {len(A)}x{len(A[0])}, B is {len(B)}x{len(B[0])}.")
                    else:
                        res = [[A[i][j] + B[i][j] for j in range(len(A[0]))] for i in range(len(A))]
                        print("\nResult (A + B):")
                        self._display_matrix(res)

                elif choice == "2":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    print("\n--- Matrix B ---")
                    B = self._input_matrix()
                    if len(A) != len(B) or len(A[0]) != len(B[0]):
                        print(f"\nError: Dimension mismatch! A is {len(A)}x{len(A[0])}, B is {len(B)}x{len(B[0])}.")
                    else:
                        res = [[A[i][j] - B[i][j] for j in range(len(A[0]))] for i in range(len(A))]
                        print("\nResult (A - B):")
                        self._display_matrix(res)

                elif choice == "3":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    print("\n--- Matrix B ---")
                    B = self._input_matrix()
                    if len(A[0]) != len(B):
                        print(f"\nError: Dimension mismatch! Cols of A ({len(A[0])}) must match Rows of B ({len(B)}).")
                    else:
                        res = [
                            [sum(A[i][k] * B[k][j] for k in range(len(A[0]))) for j in range(len(B[0]))]
                            for i in range(len(A))
                        ]
                        print("\nResult (A * B):")
                        self._display_matrix(res)

                elif choice == "4":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    res = [[A[i][j] for i in range(len(A))] for j in range(len(A[0]))]
                    print("\nResult (A^T):")
                    self._display_matrix(res)

                elif choice == "5":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    c = get_float("Enter scalar constant (c): ")
                    res = [[c * A[i][j] for j in range(len(A[0]))] for i in range(len(A))]
                    print(f"\nResult ({c} * A):")
                    self._display_matrix(res)

                elif choice == "6":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    det = self._matrix_determinant(A)
                    print(f"\nDeterminant det(A) = {self._format_number(det)}")
                    self._record_history("det(A)", det)

                elif choice == "7":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    inv = self._matrix_inverse(A)
                    print("\nInverse Matrix (A^-1):")
                    self._display_matrix(inv)

                elif choice == "8":
                    print("\n--- Matrix A ---")
                    A = self._input_matrix()
                    self._compute_eigenvalues(A)

            except Exception as e:
                print(f"\nError: {e}")

            self._pause()

    def _input_matrix(self) -> List[List[float]]:
        rows = get_int("Enter number of rows: ", min_val=1)
        cols = get_int("Enter number of columns: ", min_val=1)
        print("Enter matrix elements row by row (space-separated values):")
        matrix = []
        for i in range(rows):
            while True:
                line = input(f"  Row {i + 1} ({cols} values): ").strip()
                tokens = line.split()
                if len(tokens) != cols:
                    print(f"  Error: Expected {cols} values, got {len(tokens)}. Try again.")
                    continue
                try:
                    matrix.append([float(v) for v in tokens])
                    break
                except ValueError:
                    print("  Error: All entries must be numeric.")
        return matrix

    def _display_matrix(self, matrix: List[List[float]]):
        if not matrix or not matrix[0]:
            print("Empty Matrix")
            return
        formatted = [[self._format_number(val) for val in row] for row in matrix]
        col_widths = [max(len(formatted[r][c]) for r in range(len(matrix))) for c in range(len(matrix[0]))]
        rows = len(matrix)
        for idx, row in enumerate(formatted):
            row_str = "  ".join(val.rjust(col_widths[col]) for col, val in enumerate(row))
            if rows == 1:
                print(f"[  {row_str}  ]")
            elif idx == 0:
                print(f"/  {row_str}  \\")
            elif idx == rows - 1:
                print(f"\\  {row_str}  /")
            else:
                print(f"|  {row_str}  |")

    def _matrix_determinant(self, A: List[List[float]]) -> float:
        n = len(A)
        if n != len(A[0]):
            raise ValueError("Determinant requires a square matrix.")
        if NUMPY_AVAILABLE:
            return float(np.linalg.det(np.array(A)))
        mat = [row[:] for row in A]
        det = 1.0
        for i in range(n):
            pivot = i
            for j in range(i + 1, n):
                if abs(mat[j][i]) > abs(mat[pivot][i]):
                    pivot = j
            if pivot != i:
                mat[i], mat[pivot] = mat[pivot], mat[i]
                det *= -1.0
            if abs(mat[i][i]) < 1e-12:
                return 0.0
            det *= mat[i][i]
            for j in range(i + 1, n):
                factor = mat[j][i] / mat[i][i]
                for k in range(i + 1, n):
                    mat[j][k] -= factor * mat[i][k]
        return det

    def _matrix_inverse(self, A: List[List[float]]) -> List[List[float]]:
        n = len(A)
        if n != len(A[0]):
            raise ValueError("Inversion requires a square matrix.")
        if NUMPY_AVAILABLE:
            try:
                inv_np = np.linalg.inv(np.array(A))
                return inv_np.tolist()
            except np.linalg.LinAlgError:
                raise ValueError("Matrix is singular (non-invertible).")

        aug = [A[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        for i in range(n):
            pivot = i
            for j in range(i + 1, n):
                if abs(aug[j][i]) > abs(aug[pivot][i]):
                    pivot = j
            if abs(aug[pivot][i]) < 1e-12:
                raise ValueError("Matrix is singular (non-invertible). Determinant is 0.")
            aug[i], aug[pivot] = aug[pivot], aug[i]
            pivot_val = aug[i][i]
            for k in range(2 * n):
                aug[i][k] /= pivot_val
            for j in range(n):
                if j != i:
                    factor = aug[j][i]
                    for k in range(2 * n):
                        aug[j][k] -= factor * aug[i][k]
        return [aug[i][n:] for i in range(n)]

    def _compute_eigenvalues(self, A: List[List[float]]):
        n = len(A)
        if n != len(A[0]):
            print("\nError: Eigenvalues require a square matrix.")
            return

        if NUMPY_AVAILABLE:
            vals, vecs = np.linalg.eig(np.array(A))
            print("\nEigenvalues:")
            for idx, val in enumerate(vals):
                print(f"  λ{idx+1} = {val}")
            print("\nEigenvectors (column-wise):")
            self._display_matrix(vecs.tolist())
            return

        if n == 2:
            a, b = A[0][0], A[0][1]
            c, d = A[1][0], A[1][1]
            tr = a + d
            det = a * d - b * c
            disc = tr**2 - 4 * det
            if disc >= 0:
                l1 = (tr + math.sqrt(disc)) / 2
                l2 = (tr - math.sqrt(disc)) / 2
                print(f"\nEigenvalues: λ1 = {self._format_number(l1)}, λ2 = {self._format_number(l2)}")
            else:
                real = tr / 2
                imag = math.sqrt(-disc) / 2
                print(f"\nComplex Eigenvalues: λ1 = {real:.4f} + {imag:.4f}i, λ2 = {real:.4f} - {imag:.4f}i")
        else:
            print("\nNotice: For matrices larger than 2x2, install 'numpy' for full eigensolver support.")

    # =================================================================
    # 7. Calculus & Equation Solving
    # =================================================================
    def calculus_menu(self):
        while True:
            self._print_header("CALCULUS & EQUATION SOLVING")
            print("1. Quadratic Equation Solver (ax^2 + bx + c = 0)")
            print("2. Cubic Equation Solver (ax^3 + bx^2 + cx + d = 0)")
            print("3. Definite Integral (Simpson's 1/3 Rule)")
            print("4. Symbolic Differentiation & Integration (SymPy)")
            print("5. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-5): ").strip()
            if choice == "5":
                break

            try:
                if choice == "1":
                    a = get_float("Enter coefficient a (a != 0): ")
                    if a == 0:
                        print("Error: 'a' cannot be zero in a quadratic equation.")
                        self._pause()
                        continue
                    b = get_float("Enter coefficient b: ")
                    c = get_float("Enter coefficient c: ")
                    disc = b**2 - 4 * a * c
                    print(f"\nDiscriminant Δ = {disc}")
                    if disc > 0:
                        x1 = (-b + math.sqrt(disc)) / (2 * a)
                        x2 = (-b - math.sqrt(disc)) / (2 * a)
                        print(f"Two distinct real roots: x1 = {self._format_number(x1)}, x2 = {self._format_number(x2)}")
                    elif disc == 0:
                        x = -b / (2 * a)
                        print(f"One repeated real root: x = {self._format_number(x)}")
                    else:
                        real = -b / (2 * a)
                        imag = math.sqrt(-disc) / (2 * a)
                        print(f"Two complex roots: x1 = {real:.6g} + {imag:.6g}i, x2 = {real:.6g} - {imag:.6g}i")

                elif choice == "2":
                    a = get_float("Enter coefficient a (a != 0): ")
                    if a == 0:
                        print("Error: 'a' cannot be zero.")
                        self._pause()
                        continue
                    b = get_float("Enter coefficient b: ")
                    c = get_float("Enter coefficient c: ")
                    d = get_float("Enter coefficient d: ")
                    self._solve_cubic(a, b, c, d)

                elif choice == "3":
                    expr_str = input("Enter function f(x) (e.g., x^2 + sin(x)): ").strip()
                    a = get_float("Enter lower limit (a): ")
                    b = get_float("Enter upper limit (b): ")
                    N = 1000
                    res = self._simpson_integration(expr_str, a, b, N)
                    print(f"\nApproximate Area (Definite Integral ∫_{a}^{b} f(x) dx): {self._format_number(res)}")
                    self._record_history(f"∫({expr_str})", res)

                elif choice == "4":
                    if not SYMPY_AVAILABLE:
                        print("\nNotice: SymPy module is not installed.")
                        print("Install sympy via `pip install sympy` for full symbolic calculus.")
                    else:
                        expr_str = input("Enter expression in x (e.g., x**3 + sin(x)): ").strip()
                        x_sym = sympy.Symbol("x")
                        sym_expr = sympy.sympify(expr_str)
                        derivative = sympy.diff(sym_expr, x_sym)
                        integral = sympy.integrate(sym_expr, x_sym)
                        print(f"\nSymbolic Derivative  d/dx [{sym_expr}] = {derivative}")
                        print(f"Symbolic Indefinite Integral ∫ [{sym_expr}] dx = {integral} + C")

            except Exception as e:
                print(f"\nError: {e}")

            self._pause()

    def _solve_cubic(self, a: float, b: float, c: float, d: float):
        A, B, C = b / a, c / a, d / a
        p = B - (A**2) / 3
        q = (2 * A**3) / 27 - (A * B) / 3 + C
        disc = (q / 2) ** 2 + (p / 3) ** 3

        print(f"\nSolving cubic equation: {a}x³ + {b}x² + {c}x + {d} = 0")
        if abs(disc) < 1e-11:
            if abs(p) < 1e-11 and abs(q) < 1e-11:
                t = 0.0
                x = t - A / 3
                print(f"Three identical real roots: x = {self._format_number(x)}")
            else:
                t1 = 2 * (-q / 2) ** (1 / 3)
                t2 = -(-q / 2) ** (1 / 3)
                print(f"Real roots: x1 = {self._format_number(t1 - A/3)}, x2 = {self._format_number(t2 - A/3)}")
        elif disc < 0:
            r = math.sqrt(- (p**3) / 27)
            phi = math.acos(-q / (2 * r))
            t1 = 2 * (r ** (1 / 3)) * math.cos(phi / 3)
            t2 = 2 * (r ** (1 / 3)) * math.cos((phi + 2 * math.pi) / 3)
            t3 = 2 * (r ** (1 / 3)) * math.cos((phi + 4 * math.pi) / 3)
            print(f"Three distinct real roots:")
            print(f"  x1 = {self._format_number(t1 - A/3)}")
            print(f"  x2 = {self._format_number(t2 - A/3)}")
            print(f"  x3 = {self._format_number(t3 - A/3)}")
        else:
            u_val = -q / 2 + math.sqrt(disc)
            v_val = -q / 2 - math.sqrt(disc)
            u = math.copysign(abs(u_val) ** (1 / 3), u_val)
            v = math.copysign(abs(v_val) ** (1 / 3), v_val)
            t1 = u + v
            real_part = -(u + v) / 2 - A / 3
            imag_part = (math.sqrt(3) / 2) * (u - v)
            print(f"One real root: x1 = {self._format_number(t1 - A/3)}")
            print(f"Two complex roots: x2 = {real_part:.6g} + {imag_part:.6g}i, x3 = {real_part:.6g} - {imag_part:.6g}i")

    def _simpson_integration(self, expr_str: str, a: float, b: float, n: int) -> float:
        if n % 2 != 0:
            n += 1
        h = (b - a) / n
        evaluator = SafeMathEvaluator()

        def f(x_val: float) -> float:
            evaluator.variables["x"] = x_val
            return evaluator.evaluate(expr_str)

        integral = f(a) + f(b)
        for i in range(1, n, 2):
            integral += 4 * f(a + i * h)
        for i in range(2, n - 1, 2):
            integral += 2 * f(a + i * h)
        return integral * (h / 3)

    # =================================================================
    # 8. Geometry & Mensuration
    # =================================================================
    def geometry_menu(self):
        while True:
            self._print_header("GEOMETRY & MENSURATION")
            print("1. Circle (Area, Circumference)")
            print("2. Triangle (Area by base/height or Heron's formula)")
            print("3. Rectangle (Area, Perimeter)")
            print("4. Regular Polygon (Area, Perimeter)")
            print("5. Sphere (Volume, Surface Area)")
            print("6. Cylinder (Volume, Surface Area)")
            print("7. Cone (Volume, Surface Area)")
            print("8. Rectangular Prism (Volume, Surface Area)")
            print("9. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-9): ").strip()
            if choice == "9":
                break

            try:
                if choice == "1":
                    r = get_float("Enter radius (r > 0): ")
                    if r <= 0:
                        print("Error: Radius must be positive.")
                    else:
                        area = math.pi * r**2
                        circ = 2 * math.pi * r
                        print(f"\nCircle (r = {r}):")
                        print(f"  Area:          {self._format_number(area)}")
                        print(f"  Circumference: {self._format_number(circ)}")

                elif choice == "2":
                    print("1. Base and Height  2. Three Sides (Heron's Formula)")
                    sub = input("Select method (1-2): ").strip()
                    if sub == "1":
                        b = get_float("Enter base (b): ")
                        h = get_float("Enter height (h): ")
                        area = 0.5 * b * h
                        print(f"\nTriangle Area = {self._format_number(area)}")
                    elif sub == "2":
                        a = get_float("Enter side a: ")
                        b = get_float("Enter side b: ")
                        c = get_float("Enter side c: ")
                        if a + b <= c or a + c <= b or b + c <= a:
                            print("Error: Invalid triangle side lengths.")
                        else:
                            s = (a + b + c) / 2
                            area = math.sqrt(s * (s - a) * (s - b) * (s - c))
                            print(f"\nTriangle (a={a}, b={b}, c={c}):")
                            print(f"  Area:      {self._format_number(area)}")
                            print(f"  Perimeter: {self._format_number(a + b + c)}")

                elif choice == "3":
                    w = get_float("Enter width (w): ")
                    h = get_float("Enter height (h): ")
                    print(f"\nRectangle (w={w}, h={h}):")
                    print(f"  Area:      {self._format_number(w * h)}")
                    print(f"  Perimeter: {self._format_number(2 * (w + h))}")

                elif choice == "4":
                    n = get_int("Enter number of sides (n >= 3): ", min_val=3)
                    s = get_float("Enter side length (s > 0): ")
                    area = (n * s**2) / (4 * math.tan(math.pi / n))
                    perim = n * s
                    print(f"\nRegular Polygon (n={n}, s={s}):")
                    print(f"  Area:      {self._format_number(area)}")
                    print(f"  Perimeter: {self._format_number(perim)}")

                elif choice == "5":
                    r = get_float("Enter radius (r): ")
                    vol = (4 / 3) * math.pi * r**3
                    sa = 4 * math.pi * r**2
                    print(f"\nSphere (r={r}):")
                    print(f"  Volume:       {self._format_number(vol)}")
                    print(f"  Surface Area: {self._format_number(sa)}")

                elif choice == "6":
                    r = get_float("Enter radius (r): ")
                    h = get_float("Enter height (h): ")
                    vol = math.pi * r**2 * h
                    sa = 2 * math.pi * r * h + 2 * math.pi * r**2
                    print(f"\nCylinder (r={r}, h={h}):")
                    print(f"  Volume:       {self._format_number(vol)}")
                    print(f"  Surface Area: {self._format_number(sa)}")

                elif choice == "7":
                    r = get_float("Enter radius (r): ")
                    h = get_float("Enter height (h): ")
                    slant = math.sqrt(r**2 + h**2)
                    vol = (1 / 3) * math.pi * r**2 * h
                    sa = math.pi * r * (r + slant)
                    print(f"\nCone (r={r}, h={h}):")
                    print(f"  Volume:       {self._format_number(vol)}")
                    print(f"  Surface Area: {self._format_number(sa)}")

                elif choice == "8":
                    l = get_float("Enter length (l): ")
                    w = get_float("Enter width (w): ")
                    h = get_float("Enter height (h): ")
                    vol = l * w * h
                    sa = 2 * (l * w + l * h + w * h)
                    print(f"\nRectangular Prism (l={l}, w={w}, h={h}):")
                    print(f"  Volume:       {self._format_number(vol)}")
                    print(f"  Surface Area: {self._format_number(sa)}")

            except Exception as e:
                print(f"\nError: {e}")

            self._pause()

    # =================================================================
    # 9. Function Plotting & ASCII Charts
    # =================================================================
    def plotting_menu(self):
        while True:
            self._print_header("FUNCTION PLOTTING & ASCII CHARTS")
            print("1. Terminal ASCII Function Plotter")
            print("2. Graphical Matplotlib Plotter (Window)")
            print("3. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-3): ").strip()
            if choice == "3":
                break

            if choice == "1":
                expr_str = input("Enter function f(x) (e.g. sin(x), x^2 - 4): ").strip()
                x_min = get_float("Enter x min (e.g. -5): ")
                x_max = get_float("Enter x max (e.g. 5): ")
                if x_min >= x_max:
                    print("Error: x_min must be strictly less than x_max.")
                else:
                    self._plot_ascii(expr_str, x_min, x_max)

            elif choice == "2":
                if not MATPLOTLIB_AVAILABLE:
                    print("\nNotice: Matplotlib is not installed.")
                    print("Install via `pip install matplotlib` or use option 1 (ASCII Plotter).")
                else:
                    expr_str = input("Enter function f(x) (e.g. sin(x), x**2): ").strip()
                    x_min = get_float("Enter x min: ")
                    x_max = get_float("Enter x max: ")
                    if x_min >= x_max:
                        print("Error: x_min must be strictly less than x_max.")
                    else:
                        evaluator = SafeMathEvaluator()
                        xs = np.linspace(x_min, x_max, 500)
                        ys = []
                        for x_v in xs:
                            try:
                                evaluator.variables["x"] = float(x_v)
                                ys.append(evaluator.evaluate(expr_str))
                            except Exception:
                                ys.append(np.nan)
                        plt.figure(figsize=(8, 5))
                        plt.plot(xs, ys, label=f"f(x) = {expr_str}", color="blue", linewidth=2)
                        plt.axhline(0, color="black", linewidth=1, linestyle="--")
                        plt.axvline(0, color="black", linewidth=1, linestyle="--")
                        plt.title(f"Plot of f(x) = {expr_str}")
                        plt.xlabel("x")
                        plt.ylabel("y")
                        plt.grid(True)
                        plt.legend()
                        plt.show()

            self._pause()

    def _plot_ascii(self, expr_str: str, x_min: float, x_max: float, width: int = 55, height: int = 19):
        evaluator = SafeMathEvaluator()
        dx = (x_max - x_min) / (width - 1)
        x_vals = [x_min + i * dx for i in range(width)]
        y_vals = []

        for x in x_vals:
            try:
                evaluator.variables["x"] = x
                y = evaluator.evaluate(expr_str)
                y_vals.append(y if not (math.isnan(y) or math.isinf(y)) else None)
            except Exception:
                y_vals.append(None)

        valid_y = [y for y in y_vals if y is not None]
        if not valid_y:
            print("Error: Function produced no valid numeric values in range.")
            return

        y_min, y_max = min(valid_y), max(valid_y)
        if abs(y_max - y_min) < 1e-9:
            y_max += 1.0
            y_min -= 1.0

        grid = [[" " for _ in range(width)] for _ in range(height)]

        # Draw axis
        zero_row = int((y_max - 0) / (y_max - y_min) * (height - 1))
        if 0 <= zero_row < height:
            for c in range(width):
                grid[zero_row][c] = "-"

        zero_col = int((0 - x_min) / (x_max - x_min) * (width - 1))
        if 0 <= zero_col < width:
            for r in range(height):
                grid[r][zero_col] = "|" if grid[r][zero_col] == " " else "+"

        # Plot curve
        for c in range(width):
            y = y_vals[c]
            if y is not None:
                r = int((y_max - y) / (y_max - y_min) * (height - 1))
                if 0 <= r < height:
                    grid[r][c] = "*"

        print(f"\nASCII Plot of f(x) = {expr_str}  [y_max: {y_max:.4g}, y_min: {y_min:.4g}]")
        print("+" + "-" * width + "+")
        for row in grid:
            print("|" + "".join(row) + "|")
        print("+" + "-" * width + "+")
        print(f" x: {x_min:.4g}".ljust(width // 2) + f"x: {x_max:.4g}".rjust(width // 2))

    # =================================================================
    # 10. Date & Time Arithmetic
    # =================================================================
    def datetime_menu(self):
        while True:
            self._print_header("DATE & TIME ARITHMETIC")
            print("1. Difference Between Two Dates")
            print("2. Add or Subtract Days/Hours from a Date")
            print("3. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-3): ").strip()
            if choice == "3":
                break

            try:
                if choice == "1":
                    d1_str = input("Enter start date (YYYY-MM-DD): ").strip()
                    d2_str = input("Enter end date (YYYY-MM-DD): ").strip()
                    dt1 = datetime.datetime.strptime(d1_str, "%Y-%m-%d")
                    dt2 = datetime.datetime.strptime(d2_str, "%Y-%m-%d")
                    diff = abs(dt2 - dt1)
                    days = diff.days

                    # Calculate working days (Mon-Fri)
                    start, end = min(dt1, dt2), max(dt1, dt2)
                    cur = start
                    work_days = 0
                    while cur < end:
                        if cur.weekday() < 5:
                            work_days += 1
                        cur += datetime.timedelta(days=1)

                    print(f"\n--- Date Difference ---")
                    print(f"Total Calendar Days: {days} days")
                    print(f"Total Hours:         {days * 24} hours")
                    print(f"Working Days (M-F):  {work_days} days")

                elif choice == "2":
                    d_str = input("Enter base date (YYYY-MM-DD): ").strip()
                    dt = datetime.datetime.strptime(d_str, "%Y-%m-%d")
                    days_change = get_int("Enter days to add (or negative to subtract): ")
                    new_dt = dt + datetime.timedelta(days=days_change)
                    print(f"\nResult Date: {new_dt.strftime('%Y-%m-%d (%A)')}")

            except ValueError:
                print("Error: Invalid date format. Please use YYYY-MM-DD format.")
            except Exception as e:
                print(f"Error: {e}")

            self._pause()

    # =================================================================
    # 11. Unit & Currency Converters
    # =================================================================
    def converters_menu(self):
        while True:
            self._print_header("UNIT & CURRENCY CONVERTERS")
            print("1. Unit Converter (Length, Mass, Temp, Volume)")
            print("2. Real-Time Currency Converter")
            print("3. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-3): ").strip()
            if choice == "3":
                break

            if choice == "1":
                self.unit_converter_sub_menu()
            elif choice == "2":
                self.currency_converter_sub_menu()

    def unit_converter_sub_menu(self):
        print("\n--- Unit Converter Categories ---")
        print("1. Length (meters, km, cm, mm, miles, yards, feet, inches)")
        print("2. Mass (kg, grams, mg, pounds, ounces, metric tons)")
        print("3. Temperature (Celsius, Fahrenheit, Kelvin)")
        print("4. Volume (liters, ml, m³, gallons, quarts, cups)")
        cat = input("Select category (1-4): ").strip()

        if cat == "1":
            rates = {
                "m": 1.0,
                "km": 1000.0,
                "cm": 0.01,
                "mm": 0.001,
                "mile": 1609.344,
                "yard": 0.9144,
                "foot": 0.3048,
                "inch": 0.0254,
            }
            self._generic_unit_convert("Length", rates)
        elif cat == "2":
            rates = {
                "kg": 1.0,
                "g": 0.001,
                "mg": 0.000001,
                "lb": 0.45359237,
                "oz": 0.028349523125,
                "ton": 1000.0,
            }
            self._generic_unit_convert("Mass", rates)
        elif cat == "3":
            val = get_float("Enter temperature value: ")
            print("From: 1. Celsius  2. Fahrenheit  3. Kelvin")
            from_u = input("Select from unit (1-3): ").strip()
            print("To:   1. Celsius  2. Fahrenheit  3. Kelvin")
            to_u = input("Select to unit (1-3): ").strip()

            if from_u == "1":
                c = val
            elif from_u == "2":
                c = (val - 32) * 5 / 9
            else:
                c = val - 273.15

            if to_u == "1":
                res = c
            elif to_u == "2":
                res = (c * 9 / 5) + 32
            else:
                res = c + 273.15

            print(f"\nConverted Result = {self._format_number(res)}")

        elif cat == "4":
            rates = {
                "liter": 1.0,
                "ml": 0.001,
                "m3": 1000.0,
                "gallon": 3.78541,
                "quart": 0.946353,
                "cup": 0.24,
            }
            self._generic_unit_convert("Volume", rates)

        self._pause()

    def _generic_unit_convert(self, name: str, rates: Dict[str, float]):
        print(f"\n--- {name} Units ---")
        units = list(rates.keys())
        for idx, u in enumerate(units, 1):
            print(f"{idx}. {u}")
        from_idx = get_int("Select FROM unit #: ", min_val=1) - 1
        to_idx = get_int("Select TO unit #: ", min_val=1) - 1

        if from_idx >= len(units) or to_idx >= len(units):
            print("Invalid unit selection.")
            return

        val = get_float(f"Enter amount in {units[from_idx]}: ")
        base_val = val * rates[units[from_idx]]
        res = base_val / rates[units[to_idx]]
        print(f"\n{val} {units[from_idx]} = {self._format_number(res)} {units[to_idx]}")

    def currency_converter_sub_menu(self):
        print("\n--- Real-Time Currency Converter ---")
        print("Fetching live exchange rates...")
        url = "https://open.er-api.com/v6/latest/USD"
        rates = {}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                if data.get("result") == "success":
                    rates = data.get("rates", {})
                    print("Successfully connected to ExchangeRate API (Live rates).")
        except Exception:
            print("(Network connection unavailable. Using snapshot exchange rates).")
            rates = {
                "USD": 1.0,
                "EUR": 0.92,
                "GBP": 0.78,
                "INR": 83.5,
                "JPY": 155.0,
                "CAD": 1.36,
                "AUD": 1.51,
                "CHF": 0.90,
                "CNY": 7.23,
            }

        available = list(rates.keys())
        print(f"Available Currencies: {', '.join(available[:15])}...")
        from_curr = input("Enter FROM currency code (e.g. USD, EUR, INR): ").strip().upper()
        to_curr = input("Enter TO currency code (e.g. EUR, USD, INR): ").strip().upper()

        if from_curr not in rates or to_curr not in rates:
            print("\nError: Currency code not recognized.")
        else:
            amount = get_float(f"Enter amount in {from_curr}: ")
            usd_amount = amount / rates[from_curr]
            converted = usd_amount * rates[to_curr]
            print(f"\nResult: {amount} {from_curr} = {self._format_number(converted)} {to_curr}")

        self._pause()

    # =================================================================
    # 12. Financial Calculations
    # =================================================================
    def financial_menu(self):
        while True:
            self._print_header("FINANCIAL CALCULATIONS")
            print("1. Compound Interest & Future Value")
            print("2. Loan / Mortgage Monthly Payment")
            print("3. Net Present Value (NPV)")
            print("4. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-4): ").strip()
            if choice == "4":
                break

            try:
                if choice == "1":
                    P = get_float("Enter Principal Amount (P): ")
                    r_pct = get_float("Enter Annual Interest Rate in % (e.g., 5.5): ")
                    n = get_int("Enter Compounding frequency per year (e.g., 12 for monthly): ", min_val=1)
                    t = get_float("Enter Time in years (t): ")

                    r = r_pct / 100.0
                    A = P * ((1 + r / n) ** (n * t))
                    interest = A - P
                    print(f"\nFuture Total Value (A): {self._format_number(A)}")
                    print(f"Total Interest Earned: {self._format_number(interest)}")

                elif choice == "2":
                    P = get_float("Enter Loan Principal Amount: ")
                    r_pct = get_float("Enter Annual Interest Rate in % (e.g., 6.5): ")
                    years = get_float("Enter Loan Term in years (e.g., 30): ")

                    r_monthly = (r_pct / 100.0) / 12.0
                    n_months = years * 12.0

                    if r_monthly == 0:
                        M = P / n_months
                    else:
                        M = P * (r_monthly * (1 + r_monthly) ** n_months) / (((1 + r_monthly) ** n_months) - 1)

                    total_paid = M * n_months
                    total_interest = total_paid - P
                    print(f"\nMonthly Payment: {self._format_number(M)}")
                    print(f"Total Amount Paid: {self._format_number(total_paid)}")
                    print(f"Total Interest Paid: {self._format_number(total_interest)}")

                elif choice == "3":
                    r_pct = get_float("Enter Discount Rate in % (e.g., 10): ")
                    rate = r_pct / 100.0
                    cfs = get_float_list("Enter Cash Flows from Year 0 to N (space-separated, e.g. -1000 300 400 500): ")
                    npv = sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cfs))
                    print(f"\nNet Present Value (NPV) = {self._format_number(npv)}")
                    if npv > 0:
                        print("Investment Decision: Financially Viable (NPV > 0)")
                    else:
                        print("Investment Decision: Not Viable (NPV <= 0)")

            except Exception as e:
                print(f"\nError: {e}")

            self._pause()

    # =================================================================
    # 13. Statistical Calculations & Regression
    # =================================================================
    def statistics_menu(self):
        while True:
            self._print_header("STATISTICAL CALCULATIONS")
            print("1. Descriptive Statistics (Mean, Median, Std Dev, etc.)")
            print("2. Linear Regression (y = mx + b)")
            print("3. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-3): ").strip()
            if choice == "3":
                break

            try:
                if choice == "1":
                    data = get_float_list("Enter numeric dataset (space-separated values): ")
                    n = len(data)
                    mean_v = statistics.mean(data)
                    median_v = statistics.median(data)
                    try:
                        mode_v = self._format_number(statistics.mode(data))
                    except statistics.StatisticsError:
                        mode_v = "No unique mode"

                    stdev_v = statistics.stdev(data) if n > 1 else 0.0
                    variance_v = statistics.variance(data) if n > 1 else 0.0

                    print(f"\n--- Summary Statistics (N = {n}) ---")
                    print(f"Mean:               {self._format_number(mean_v)}")
                    print(f"Median:             {self._format_number(median_v)}")
                    print(f"Mode:               {mode_v}")
                    print(f"Min / Max:          {self._format_number(min(data))} / {self._format_number(max(data))}")
                    print(f"Range:              {self._format_number(max(data) - min(data))}")
                    print(f"Sample Std Dev:     {self._format_number(stdev_v)}")
                    print(f"Sample Variance:    {self._format_number(variance_v)}")

                elif choice == "2":
                    x_vals = get_float_list("Enter X values (space-separated): ")
                    y_vals = get_float_list("Enter Y values (space-separated): ")

                    if len(x_vals) != len(y_vals) or len(x_vals) < 2:
                        print("Error: X and Y datasets must have equal length (minimum 2 data points).")
                    else:
                        n = len(x_vals)
                        sum_x = sum(x_vals)
                        sum_y = sum(y_vals)
                        sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
                        sum_x2 = sum(x**2 for x in x_vals)
                        sum_y2 = sum(y**2 for y in y_vals)

                        denom = n * sum_x2 - sum_x**2
                        if denom == 0:
                            print("Error: Vertical line detected (X values are identical).")
                        else:
                            m = (n * sum_xy - sum_x * sum_y) / denom
                            b = (sum_y - m * sum_x) / n

                            num_r = n * sum_xy - sum_x * sum_y
                            den_r = math.sqrt((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2))
                            r = num_r / den_r if den_r != 0 else 0.0

                            print(f"\nLine of Best Fit:  y = {self._format_number(m)} * x + {self._format_number(b)}")
                            print(f"Slope (m):        {self._format_number(m)}")
                            print(f"Intercept (b):    {self._format_number(b)}")
                            print(f"Correlation (r):  {self._format_number(r)}")
                            print(f"R-squared (R²):   {self._format_number(r**2)}")

            except Exception as e:
                print(f"\nError: {e}")

            self._pause()

    # =================================================================
    # 14. Probability, Dice & Randomness
    # =================================================================
    def probability_menu(self):
        while True:
            self._print_header("PROBABILITY & RANDOMNESS")
            print("1. Roll Dice (NdS)")
            print("2. Flip Coins (N flips)")
            print("3. Generate Secure Random Password")
            print("4. Random Sample / Shuffle List")
            print("5. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-5): ").strip()
            if choice == "5":
                break

            if choice == "1":
                num_dice = get_int("Enter number of dice: ", min_val=1)
                sides = get_int("Enter sides per die (e.g. 6, 20): ", min_val=2)
                rolls = [random.randint(1, sides) for _ in range(num_dice)]
                print(f"\nRolled {num_dice}d{sides}: {rolls}")
                print(f"Total Sum: {sum(rolls)}")

            elif choice == "2":
                n = get_int("Enter number of coin flips: ", min_val=1)
                flips = [random.choice(["Heads", "Tails"]) for _ in range(n)]
                heads = flips.count("Heads")
                tails = flips.count("Tails")
                print(f"\nFlipped {n} coins:")
                print(f"  Heads: {heads} ({heads/n*100:.1f}%)")
                print(f"  Tails: {tails} ({tails/n*100:.1f}%)")

            elif choice == "3":
                length = get_int("Enter password length: ", min_val=4)
                alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-="
                pwd = "".join(secrets.choice(alphabet) for _ in range(length))
                print(f"\nGenerated Secure Password: {pwd}")

            elif choice == "4":
                raw = input("Enter list items separated by spaces: ").strip().split()
                if not raw:
                    print("Error: Empty list.")
                else:
                    k = get_int(f"Enter sample size (1 to {len(raw)}): ", min_val=1)
                    if k > len(raw):
                        print("Error: Sample size exceeds list size.")
                    else:
                        sample = random.sample(raw, k)
                        print(f"\nRandom Sample ({k} items): {sample}")

            self._pause()

    # =================================================================
    # 15. Health & Fitness Metrics
    # =================================================================
    def fitness_menu(self):
        while True:
            self._print_header("HEALTH & FITNESS METRICS")
            print("1. Body Mass Index (BMI)")
            print("2. Basal Metabolic Rate (BMR) & TDEE")
            print("3. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-3): ").strip()
            if choice == "3":
                break

            if choice == "1":
                weight_kg = get_float("Enter weight in kg: ")
                height_cm = get_float("Enter height in cm: ")
                if weight_kg <= 0 or height_cm <= 0:
                    print("Error: Height and weight must be positive.")
                else:
                    height_m = height_cm / 100.0
                    bmi = weight_kg / (height_m**2)

                    if bmi < 18.5:
                        cat = "Underweight"
                    elif 18.5 <= bmi < 25.0:
                        cat = "Normal weight"
                    elif 25.0 <= bmi < 30.0:
                        cat = "Overweight"
                    else:
                        cat = "Obese"

                    print(f"\nBMI Score: {bmi:.2f}")
                    print(f"Category:  {cat}")

            elif choice == "2":
                gender = input("Enter gender (M/F): ").strip().upper()
                weight_kg = get_float("Enter weight in kg: ")
                height_cm = get_float("Enter height in cm: ")
                age = get_int("Enter age in years: ", min_val=1)

                if gender == "M":
                    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
                else:
                    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

                print("\nActivity Levels:")
                print(" 1. Sedentary (little/no exercise)")
                print(" 2. Lightly Active (1-3 days/wk)")
                print(" 3. Moderately Active (3-5 days/wk)")
                print(" 4. Very Active (6-7 days/wk)")
                act_ch = input("Select activity level (1-4): ").strip()
                mults = {"1": 1.2, "2": 1.375, "3": 1.55, "4": 1.725}
                tdee = bmr * mults.get(act_ch, 1.2)

                print(f"\nBasal Metabolic Rate (BMR): {bmr:.0f} kcal/day")
                print(f"Total Daily Energy Expenditure (TDEE): {tdee:.0f} kcal/day")

            self._pause()

    # =================================================================
    # 16. History Memory & Settings
    # =================================================================
    def history_settings_menu(self):
        while True:
            self._print_header("HISTORY & SETTINGS")
            print(f"1. View Calculation History (Total: {len(self.history)})")
            print("2. Clear History")
            print(f"3. Toggle Angle Unit (Current: {self.angle_unit.title()})")
            print("4. Back to Main Menu")
            print("=" * 60)

            choice = input("Select an option (1-4): ").strip()
            if choice == "4":
                break

            if choice == "1":
                print("\n--- Calculation History ---")
                if not self.history:
                    print("History is empty.")
                else:
                    for idx, (expr, res) in enumerate(self.history[-15:], 1):
                        print(f" [{idx}] {expr} = {res}")
            elif choice == "2":
                self.history.clear()
                print("\nCalculation history cleared.")
            elif choice == "3":
                self.angle_unit = "radians" if self.angle_unit == "degrees" else "degrees"
                print(f"\nAngle unit updated to: {self.angle_unit.title()}")

            self._pause()


if __name__ == "__main__":
    calculator = AdvancedCalculator()
    calculator.run()
