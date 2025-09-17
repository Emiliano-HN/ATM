#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import hashlib
import getpass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

class TipoTransaccion(Enum):
    """Tipos de transacciones disponibles"""
    RETIRO = "RETIRO"
    DEPOSITO = "DEPOSITO"
    CONSULTA = "CONSULTA"
    CAMBIO_PIN = "CAMBIO_PIN"
    LOGIN = "LOGIN"

class EstadoTransaccion(Enum):
    """Estados posibles de una transacción"""
    EXITOSA = "EXITOSA"
    FALLIDA = "FALLIDA"
    CANCELADA = "CANCELADA"

class ConfiguracionATM:
    """Configuración global del ATM"""
    SALDO_INICIAL = 0
    LIMITE_RETIRO_DIARIO = 200000
    LIMITE_RETIRO_TRANSACCION = 50000
    MONTOS_RAPIDOS = [5000, 10000, 15000, 20000, 50000]
    INTENTOS_PIN_MAXIMOS = 3
    ARCHIVO_DATOS = "datos_atm.json"
    ARCHIVO_LOGS = "logs_transacciones.log"

class SistemaSeguridad:
    """Maneja la seguridad del sistema"""
    
    @staticmethod
    def hash_pin(pin: str) -> str:
        """Hashea el PIN para almacenamiento seguro"""
        return hashlib.sha256(pin.encode()).hexdigest()
    
    @staticmethod
    def verificar_pin(pin: str, pin_hasheado: str) -> bool:
        """Verifica si el PIN es correcto"""
        return SistemaSeguridad.hash_pin(pin) == pin_hasheado
    
    @staticmethod
    def validar_formato_pin(pin: str) -> bool:
        """Valida que el PIN tenga el formato correcto"""
        return pin.isdigit() and len(pin) == 4

class Transaccion:
    """Representa una transacción del ATM"""
    
    def __init__(self, tipo: TipoTransaccion, monto: float = 0, 
                 estado: EstadoTransaccion = EstadoTransaccion.EXITOSA,
                 cuenta: str = "N/A", detalle: str = ""):
        self.timestamp = datetime.now()
        self.tipo = tipo
        self.monto = monto
        self.estado = estado
        self.cuenta = cuenta
        self.detalle = detalle
    
    def to_dict(self) -> Dict:
        """Convierte la transacción a diccionario para JSON"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'tipo': self.tipo.value,
            'monto': self.monto,
            'estado': self.estado.value,
            'cuenta': self.cuenta,
            'detalle': self.detalle
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Crea una transacción desde un diccionario"""
        transaccion = cls(
            TipoTransaccion(data['tipo']),
            data['monto'],
            EstadoTransaccion(data['estado']),
            data['cuenta'],
            data['detalle']
        )
        transaccion.timestamp = datetime.fromisoformat(data['timestamp'])
        return transaccion
    
    def __str__(self) -> str:
        fecha_str = self.timestamp.strftime("%d/%m/%Y %H:%M:%S")
        if self.monto > 0:
            return f"{fecha_str} | {self.cuenta} | {self.tipo.value} por ${self.monto:,.2f} | {self.estado.value}"
        else:
            return f"{fecha_str} | {self.cuenta} | {self.tipo.value} | {self.estado.value}"

class CuentaUsuario:
    """Representa una cuenta de usuario"""
    
    def __init__(self, numero_cuenta: str, pin: str, saldo_inicial: float = 0):
        self.numero_cuenta = numero_cuenta
        self.pin_hash = SistemaSeguridad.hash_pin(pin)
        self.saldo = saldo_inicial
        self.bloqueada = False
        self.intentos_fallidos = 0
        self.ultimo_retiro_fecha = None
        self.retiros_diarios = 0
        self.fecha_creacion = datetime.now()
    
    def verificar_pin(self, pin: str) -> bool:
        """Verifica el PIN de la cuenta"""
        return SistemaSeguridad.verificar_pin(pin, self.pin_hash)
    
    def cambiar_pin(self, pin_actual: str, pin_nuevo: str) -> bool:
        """Cambia el PIN de la cuenta"""
        if self.verificar_pin(pin_actual) and SistemaSeguridad.validar_formato_pin(pin_nuevo):
            self.pin_hash = SistemaSeguridad.hash_pin(pin_nuevo)
            return True
        return False
    
    def puede_retirar(self, monto: float) -> Tuple[bool, str]:
        """Verifica si se puede realizar el retiro"""
        if self.saldo < monto:
            return False, "Saldo insuficiente"
        
        if monto > ConfiguracionATM.LIMITE_RETIRO_TRANSACCION:
            return False, f"Monto excede límite por transacción (${ConfiguracionATM.LIMITE_RETIRO_TRANSACCION:,})"
        
        # Verificar límite diario
        hoy = datetime.now().date()
        if self.ultimo_retiro_fecha != hoy:
            self.retiros_diarios = 0
            self.ultimo_retiro_fecha = hoy
        
        if self.retiros_diarios + monto > ConfiguracionATM.LIMITE_RETIRO_DIARIO:
            return False, f"Excede límite diario de retiros (${ConfiguracionATM.LIMITE_RETIRO_DIARIO:,})"
        
        return True, "OK"
    
    def retirar(self, monto: float) -> bool:
        """Realiza un retiro de la cuenta"""
        puede, mensaje = self.puede_retirar(monto)
        if puede:
            self.saldo -= monto
            self.retiros_diarios += monto
            return True
        return False
    
    def depositar(self, monto: float) -> bool:
        """Realiza un depósito en la cuenta"""
        if monto > 0:
            self.saldo += monto
            return True
        return False
    
    def to_dict(self) -> Dict:
        """Convierte la cuenta a diccionario para JSON"""
        return {
            'numero_cuenta': self.numero_cuenta,
            'pin_hash': self.pin_hash,
            'saldo': self.saldo,
            'bloqueada': self.bloqueada,
            'intentos_fallidos': self.intentos_fallidos,
            'ultimo_retiro_fecha': self.ultimo_retiro_fecha.isoformat() if self.ultimo_retiro_fecha else None,
            'retiros_diarios': self.retiros_diarios,
            'fecha_creacion': self.fecha_creacion.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Crea una cuenta desde un diccionario"""
        cuenta = cls.__new__(cls)
        cuenta.numero_cuenta = data['numero_cuenta']
        cuenta.pin_hash = data['pin_hash']
        cuenta.saldo = data['saldo']
        cuenta.bloqueada = data['bloqueada']
        cuenta.intentos_fallidos = data['intentos_fallidos']
        cuenta.ultimo_retiro_fecha = datetime.fromisoformat(data['ultimo_retiro_fecha']).date() if data['ultimo_retiro_fecha'] else None
        cuenta.retiros_diarios = data['retiros_diarios']
        cuenta.fecha_creacion = datetime.fromisoformat(data['fecha_creacion'])
        return cuenta

class GestorDatos:
    """Maneja la persistencia de datos"""
    
    @staticmethod
    def cargar_datos() -> Tuple[Dict[str, CuentaUsuario], List[Transaccion]]:
        """Carga datos desde archivo JSON"""
        cuentas = {}
        transacciones = []
        
        if os.path.exists(ConfiguracionATM.ARCHIVO_DATOS):
            try:
                with open(ConfiguracionATM.ARCHIVO_DATOS, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Cargar cuentas
                for cuenta_data in data.get('cuentas', []):
                    cuenta = CuentaUsuario.from_dict(cuenta_data)
                    cuentas[cuenta.numero_cuenta] = cuenta
                
                # Cargar transacciones
                for trans_data in data.get('transacciones', []):
                    transacciones.append(Transaccion.from_dict(trans_data))
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Error cargando datos: {e}")
        
        return cuentas, transacciones
    
    @staticmethod
    def guardar_datos(cuentas: Dict[str, CuentaUsuario], transacciones: List[Transaccion]):
        """Guarda datos en archivo JSON"""
        try:
            data = {
                'cuentas': [cuenta.to_dict() for cuenta in cuentas.values()],
                'transacciones': [trans.to_dict() for trans in transacciones[-1000:]]  # Mantener últimas 1000
            }
            
            with open(ConfiguracionATM.ARCHIVO_DATOS, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except IOError as e:
            print(f"Error guardando datos: {e}")

class InterfazUsuario:
    """Maneja la interfaz de usuario"""
    
    @staticmethod
    def limpiar_pantalla():
        """Limpia la pantalla"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def mostrar_titulo(titulo: str):
        """Muestra un título formateado"""
        print("\n" + "="*50)
        print(f"{titulo:^50}")
        print("="*50)
    
    @staticmethod
    def mostrar_menu(titulo: str, opciones: List[str]) -> str:
        """Muestra un menú y retorna la opción seleccionada"""
        InterfazUsuario.mostrar_titulo(titulo)
        
        for i, opcion in enumerate(opciones, 1):
            print(f"({i}) {opcion}")
        
        while True:
            try:
                opcion = input("\nSeleccione una opción: ").strip()
                if opcion.isdigit() and 1 <= int(opcion) <= len(opciones):
                    return opcion
                print("Opción inválida. Intente nuevamente.")
            except KeyboardInterrupt:
                print("\n\nOperación cancelada por el usuario.")
                return str(len(opciones))  # Retorna última opción (generalmente salir)
    
    @staticmethod
    def solicitar_pin(mensaje: str = "Ingrese su PIN de 4 dígitos: ") -> str:
        """Solicita el PIN de forma segura"""
        while True:
            try:
                pin = getpass.getpass(mensaje)
                if SistemaSeguridad.validar_formato_pin(pin):
                    return pin
                print("El PIN debe tener exactamente 4 dígitos.")
            except KeyboardInterrupt:
                return ""
    
    @staticmethod
    def solicitar_monto(mensaje: str) -> Optional[float]:
        """Solicita un monto al usuario"""
        while True:
            try:
                entrada = input(f"\n{mensaje} (o 'q' para cancelar): $").strip()
                if entrada.lower() == 'q':
                    return None
                
                monto = float(entrada.replace(',', ''))
                if monto <= 0:
                    print("El monto debe ser mayor que cero.")
                    continue
                    
                return monto
                
            except ValueError:
                print("Ingrese un monto válido.")
            except KeyboardInterrupt:
                return None
    
    @staticmethod
    def confirmar_operacion(mensaje: str) -> bool:
        """Solicita confirmación al usuario"""
        while True:
            try:
                respuesta = input(f"\n{mensaje} (S/N): ").strip().upper()
                if respuesta in ['S', 'SI', 'Y', 'YES']:
                    return True
                elif respuesta in ['N', 'NO']:
                    return False
                print("Responda con S (Sí) o N (No).")
            except KeyboardInterrupt:
                return False

class CajeroAutomatico:
    """Clase principal del cajero automático"""
    
    def __init__(self):
        self.cuentas, self.transacciones = GestorDatos.cargar_datos()
        self.cuenta_actual = None
        self.sesion_activa = False
        
        # Crear cuenta demo si no existen cuentas
        if not self.cuentas:
            self.crear_cuenta_demo()
    
    def crear_cuenta_demo(self):
        """Crea una cuenta demo para pruebas"""
        cuenta_demo = CuentaUsuario("123456", "1234", 100000)
        self.cuentas["123456"] = cuenta_demo
        print("  Cuenta demo creada:")
        print("   Número: 123456")
        print("   PIN: 1234")
        print("   Saldo inicial: $100,000")
        self.guardar_datos()
    
    def registrar_transaccion(self, tipo: TipoTransaccion, monto: float = 0, 
                            estado: EstadoTransaccion = EstadoTransaccion.EXITOSA, 
                            detalle: str = ""):
        """Registra una transacción"""
        cuenta_id = self.cuenta_actual.numero_cuenta if self.cuenta_actual else "SISTEMA"
        transaccion = Transaccion(tipo, monto, estado, cuenta_id, detalle)
        self.transacciones.append(transaccion)
        
        # Log también en archivo de texto para compatibilidad
        try:
            with open("registroTransacciones.txt", "a", encoding='utf-8') as f:
                f.write(f"\n{transaccion}")
        except IOError:
            pass
    
    def guardar_datos(self):
        """Guarda todos los datos"""
        GestorDatos.guardar_datos(self.cuentas, self.transacciones)
    
    def autenticar_usuario(self) -> bool:
        """Autentica un usuario"""
        InterfazUsuario.mostrar_titulo("AUTENTICACIÓN DE USUARIO")
        
        numero_cuenta = input("Número de cuenta: ").strip()
        
        if numero_cuenta not in self.cuentas:
            print("Cuenta no encontrada.")
            self.registrar_transaccion(TipoTransaccion.LOGIN, estado=EstadoTransaccion.FALLIDA, 
                                     detalle=f"Cuenta inexistente: {numero_cuenta}")
            return False
        
        cuenta = self.cuentas[numero_cuenta]
        
        if cuenta.bloqueada:
            print("Cuenta bloqueada por seguridad. Contacte al administrador.")
            return False
        
        # Solicitar PIN
        for intento in range(ConfiguracionATM.INTENTOS_PIN_MAXIMOS):
            pin = InterfazUsuario.solicitar_pin()
            if not pin:  # Usuario canceló
                return False
                
            if cuenta.verificar_pin(pin):
                self.cuenta_actual = cuenta
                self.sesion_activa = True
                cuenta.intentos_fallidos = 0
                self.registrar_transaccion(TipoTransaccion.LOGIN, detalle="Login exitoso")
                print(f"Bienvenido, cuenta {numero_cuenta}")
                return True
            else:
                intentos_restantes = ConfiguracionATM.INTENTOS_PIN_MAXIMOS - intento - 1
                cuenta.intentos_fallidos += 1
                
                if intentos_restantes > 0:
                    print(f"PIN incorrecto. Le quedan {intentos_restantes} intentos.")
                else:
                    cuenta.bloqueada = True
                    print("PIN incorrecto. Cuenta bloqueada por seguridad.")
                    self.registrar_transaccion(TipoTransaccion.LOGIN, estado=EstadoTransaccion.FALLIDA,
                                             detalle="Cuenta bloqueada por intentos fallidos")
                
                self.guardar_datos()
        
        return False
    
    def menu_retiro(self):
        """Maneja el menú de retiros"""
        opciones = []
        for monto in ConfiguracionATM.MONTOS_RAPIDOS:
            opciones.append(f"${monto:,}")
        opciones.extend(["Otro monto", "Volver"])
        
        while True:
            opcion = InterfazUsuario.mostrar_menu("RETIRO DE DINERO", opciones)
            
            if opcion == str(len(opciones)):  # Volver
                break
            elif opcion == str(len(opciones) - 1):  # Otro monto
                monto = InterfazUsuario.solicitar_monto("Ingrese el monto a retirar")
                if monto:
                    self.procesar_retiro(monto)
                break
            else:
                idx = int(opcion) - 1
                if 0 <= idx < len(ConfiguracionATM.MONTOS_RAPIDOS):
                    monto = ConfiguracionATM.MONTOS_RAPIDOS[idx]
                    self.procesar_retiro(monto)
                break
    
    def procesar_retiro(self, monto: float):
        """Procesa un retiro"""
        puede, mensaje = self.cuenta_actual.puede_retirar(monto)
        
        if not puede:
            print(f"No se puede realizar el retiro: {mensaje}")
            self.registrar_transaccion(TipoTransaccion.RETIRO, monto, EstadoTransaccion.FALLIDA, mensaje)
            return
        
        # Confirmar operación
        if InterfazUsuario.confirmar_operacion(f"¿Confirma el retiro de ${monto:,.2f}?"):
            if self.cuenta_actual.retirar(monto):
                print(f"Retiro exitoso de ${monto:,.2f}")
                print(f"Saldo actual: ${self.cuenta_actual.saldo:,.2f}")
                self.registrar_transaccion(TipoTransaccion.RETIRO, monto)
                self.guardar_datos()
            else:
                print("Error procesando el retiro.")
                self.registrar_transaccion(TipoTransaccion.RETIRO, monto, EstadoTransaccion.FALLIDA)
        else:
            print("Operación cancelada.")
            self.registrar_transaccion(TipoTransaccion.RETIRO, monto, EstadoTransaccion.CANCELADA)
    
    def procesar_deposito(self):
        """Procesa un depósito"""
        monto = InterfazUsuario.solicitar_monto("Ingrese el monto a depositar")
        if not monto:
            return
        
        if InterfazUsuario.confirmar_operacion(f"¿Confirma el depósito de ${monto:,.2f}?"):
            if self.cuenta_actual.depositar(monto):
                print(f"Depósito exitoso de ${monto:,.2f}")
                print(f"Saldo actual: ${self.cuenta_actual.saldo:,.2f}")
                self.registrar_transaccion(TipoTransaccion.DEPOSITO, monto)
                self.guardar_datos()
            else:
                print("Error procesando el depósito.")
                self.registrar_transaccion(TipoTransaccion.DEPOSITO, monto, EstadoTransaccion.FALLIDA)
        else:
            print("Operación cancelada.")
            self.registrar_transaccion(TipoTransaccion.DEPOSITO, monto, EstadoTransaccion.CANCELADA)
    
    def consultar_saldo(self):
        """Muestra el saldo de la cuenta"""
        print(f"Su saldo actual es: ${self.cuenta_actual.saldo:,.2f}")
        
        # Mostrar información adicional
        limite_disponible = ConfiguracionATM.LIMITE_RETIRO_DIARIO - self.cuenta_actual.retiros_diarios
        print(f"Límite de retiro diario disponible: ${limite_disponible:,.2f}")
        
        self.registrar_transaccion(TipoTransaccion.CONSULTA)
    
    def cambiar_pin(self):
        """Permite cambiar el PIN"""
        InterfazUsuario.mostrar_titulo("CAMBIO DE PIN")
        
        pin_actual = InterfazUsuario.solicitar_pin("Ingrese su PIN actual: ")
        if not pin_actual:
            return
        
        pin_nuevo = InterfazUsuario.solicitar_pin("Ingrese su nuevo PIN: ")
        if not pin_nuevo:
            return
        
        pin_confirmacion = InterfazUsuario.solicitar_pin("Confirme su nuevo PIN: ")
        if pin_nuevo != pin_confirmacion:
            print("Los PINs no coinciden.")
            return
        
        if self.cuenta_actual.cambiar_pin(pin_actual, pin_nuevo):
            print("PIN cambiado exitosamente.")
            self.registrar_transaccion(TipoTransaccion.CAMBIO_PIN)
            self.guardar_datos()
        else:
            print("PIN actual incorrecto o nuevo PIN inválido.")
            self.registrar_transaccion(TipoTransaccion.CAMBIO_PIN, estado=EstadoTransaccion.FALLIDA)
    
    def menu_usuario(self):
        """Menú principal del usuario"""
        opciones = [
            "Retiro",
            "Depósito", 
            "Consulta de saldo",
            "Cambiar PIN",
            "Cerrar sesión"
        ]
        
        while self.sesion_activa:
            opcion = InterfazUsuario.mostrar_menu(
                f"CAJERO AUTOMÁTICO - Cuenta: {self.cuenta_actual.numero_cuenta}", 
                opciones
            )
            
            if opcion == "1":
                self.menu_retiro()
            elif opcion == "2":
                self.procesar_deposito()
            elif opcion == "3":
                self.consultar_saldo()
            elif opcion == "4":
                self.cambiar_pin()
            elif opcion == "5":
                self.cerrar_sesion()
                break
            
            if self.sesion_activa:
                input("\nPresione Enter para continuar...")
    
    def cerrar_sesion(self):
        """Cierra la sesión actual"""
        if InterfazUsuario.confirmar_operacion("¿Desea cerrar la sesión?"):
            self.sesion_activa = False
            self.cuenta_actual = None
            print("Sesión cerrada. ¡Gracias por usar nuestros servicios!")

class AdministradorATM:
    """Clase para funcionalidades de administrador"""
    
    def __init__(self, cajero: CajeroAutomatico):
        self.cajero = cajero
        self.pin_admin = "0000"  # En producción debería estar hasheado y ser más seguro
    
    def autenticar_admin(self) -> bool:
        """Autentica al administrador"""
        InterfazUsuario.mostrar_titulo("ACCESO DE ADMINISTRADOR")
        
        pin = InterfazUsuario.solicitar_pin("PIN de administrador: ")
        if pin == self.pin_admin:
            print("Acceso de administrador autorizado")
            return True
        else:
            print("PIN de administrador incorrecto")
            return False
    
    def ver_estadisticas(self):
        """Muestra estadísticas del sistema"""
        InterfazUsuario.mostrar_titulo("ESTADÍSTICAS DEL SISTEMA")
        
        total_cuentas = len(self.cajero.cuentas)
        cuentas_bloqueadas = sum(1 for c in self.cajero.cuentas.values() if c.bloqueada)
        total_saldo = sum(c.saldo for c in self.cajero.cuentas.values())
        
        print(f"Total de cuentas: {total_cuentas}")
        print(f"Cuentas bloqueadas: {cuentas_bloqueadas}")
        print(f"Saldo total del sistema: ${total_saldo:,.2f}")
        
        # Estadísticas de transacciones
        if self.cajero.transacciones:
            hoy = datetime.now().date()
            transacciones_hoy = [t for t in self.cajero.transacciones if t.timestamp.date() == hoy]
            
            print(f"Transacciones del día: {len(transacciones_hoy)}")
            
            # Transacciones por tipo
            tipos_count = {}
            for trans in transacciones_hoy:
                tipos_count[trans.tipo.value] = tipos_count.get(trans.tipo.value, 0) + 1
            
            for tipo, count in tipos_count.items():
                print(f"   {tipo}: {count}")
    
    def ver_logs_transacciones(self):
        """Muestra el log de transacciones"""
        InterfazUsuario.mostrar_titulo("REGISTRO DE TRANSACCIONES")
        
        if not self.cajero.transacciones:
            print("No hay transacciones registradas")
            return
        
        # Mostrar últimas 50 transacciones
        ultimas_transacciones = self.cajero.transacciones[-50:]
        
        print(f"Mostrando últimas {len(ultimas_transacciones)} transacciones:\n")
        for trans in reversed(ultimas_transacciones):
            print(f"  {trans}")
    
    def gestionar_cuentas(self):
        """Permite gestionar las cuentas"""
        opciones = [
            "Listar todas las cuentas",
            "Desbloquear cuenta",
            "Crear nueva cuenta",
            "Volver"
        ]
        
        while True:
            opcion = InterfazUsuario.mostrar_menu("GESTIÓN DE CUENTAS", opciones)
            
            if opcion == "1":
                self.listar_cuentas()
            elif opcion == "2":
                self.desbloquear_cuenta()
            elif opcion == "3":
                self.crear_cuenta()
            elif opcion == "4":
                break
            
            input("\nPresione Enter para continuar...")
    
    def listar_cuentas(self):
        """Lista todas las cuentas"""
        if not self.cajero.cuentas:
            print("No hay cuentas registradas")
            return
        
        print("\nLISTA DE CUENTAS:")
        print("-" * 80)
        print(f"{'Cuenta':<10} {'Saldo':<15} {'Estado':<12} {'Fecha Creación':<20}")
        print("-" * 80)
        
        for cuenta in self.cajero.cuentas.values():
            estado = "BLOQUEADA" if cuenta.bloqueada else "✅ ACTIVA"
            fecha = cuenta.fecha_creacion.strftime("%d/%m/%Y %H:%M")
            print(f"{cuenta.numero_cuenta:<10} ${cuenta.saldo:<14,.2f} {estado:<12} {fecha}")
    
    def desbloquear_cuenta(self):
        """Desbloquea una cuenta"""
        numero_cuenta = input("Número de cuenta a desbloquear: ").strip()
        
        if numero_cuenta not in self.cajero.cuentas:
            print("Cuenta no encontrada")
            return
        
        cuenta = self.cajero.cuentas[numero_cuenta]
        
        if not cuenta.bloqueada:
            print("La cuenta ya está desbloqueada")
            return
        
        if InterfazUsuario.confirmar_operacion(f"¿Desbloquear la cuenta {numero_cuenta}?"):
            cuenta.bloqueada = False
            cuenta.intentos_fallidos = 0
            self.cajero.guardar_datos()
            print("Cuenta desbloqueada exitosamente")
    
    def crear_cuenta(self):
        """Crea una nueva cuenta"""
        InterfazUsuario.mostrar_titulo("CREAR NUEVA CUENTA")
        
        numero_cuenta = input("Número de cuenta (6 dígitos): ").strip()
        
        if not numero_cuenta.isdigit() or len(numero_cuenta) != 6:
            print("El número de cuenta debe tener 6 dígitos")
            return
        
        if numero_cuenta in self.cajero.cuentas:
            print("Ya existe una cuenta con ese número")
            return
        
        pin = InterfazUsuario.solicitar_pin("PIN inicial para la cuenta: ")
        if not pin:
            return
        
        try:
            saldo_inicial = float(input("Saldo inicial (opcional, presione Enter para $0): ") or "0")
            if saldo_inicial < 0:
                print("El saldo inicial no puede ser negativo")
                return
        except ValueError:
            print("Saldo inválido")
            return
        
        cuenta = CuentaUsuario(numero_cuenta, pin, saldo_inicial)
        self.cajero.cuentas[numero_cuenta] = cuenta
        self.cajero.guardar_datos()
        
        print(f"Cuenta {numero_cuenta} creada exitosamente")
        print(f"Saldo inicial: ${saldo_inicial:,.2f}")
    
    def limpiar_logs(self):
        """Limpia el registro de transacciones"""
        if not self.cajero.transacciones:
            print("No hay transacciones para limpiar")
            return
        
        total = len(self.cajero.transacciones)
        if InterfazUsuario.confirmar_operacion(f"¿Eliminar todas las {total} transacciones registradas?"):
            self.cajero.transacciones.clear()
            self.cajero.guardar_datos()
            
            # Limpiar también el archivo de texto
            try:
                with open("registroTransacciones.txt", "w") as f:
                    f.write("")
                print("Registro de transacciones limpiado exitosamente")
            except IOError:
                print("Transacciones eliminadas, pero no se pudo limpiar el archivo de texto")
    
    def exportar_datos(self):
        """Exporta datos del sistema"""
        InterfazUsuario.mostrar_titulo("EXPORTAR DATOS")
        
        opciones = [
            "Exportar transacciones a CSV",
            "Exportar cuentas a CSV", 
            "Generar reporte completo",
            "Volver"
        ]
        
        opcion = InterfazUsuario.mostrar_menu("OPCIONES DE EXPORTACIÓN", opciones)
        
        if opcion == "1":
            self.exportar_transacciones_csv()
        elif opcion == "2":
            self.exportar_cuentas_csv()
        elif opcion == "3":
            self.generar_reporte_completo()
    
    def exportar_transacciones_csv(self):
        """Exporta transacciones a archivo CSV"""
        try:
            import csv
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo = f"transacciones_{fecha}.csv"
            
            with open(archivo, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Fecha', 'Hora', 'Cuenta', 'Tipo', 'Monto', 'Estado', 'Detalle'])
                
                for trans in self.cajero.transacciones:
                    fecha_str = trans.timestamp.strftime("%d/%m/%Y")
                    hora_str = trans.timestamp.strftime("%H:%M:%S")
                    writer.writerow([
                        fecha_str, hora_str, trans.cuenta, trans.tipo.value, 
                        trans.monto, trans.estado.value, trans.detalle
                    ])
            
            print(f"Transacciones exportadas a: {archivo}")
            
        except ImportError:
            print("Módulo CSV no disponible")
        except IOError as e:
            print(f"Error exportando datos: {e}")
    
    def exportar_cuentas_csv(self):
        """Exporta información de cuentas a CSV"""
        try:
            import csv
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo = f"cuentas_{fecha}.csv"
            
            with open(archivo, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Numero_Cuenta', 'Saldo', 'Estado', 'Fecha_Creacion', 'Retiros_Diarios'])
                
                for cuenta in self.cajero.cuentas.values():
                    estado = "BLOQUEADA" if cuenta.bloqueada else "ACTIVA"
                    fecha_creacion = cuenta.fecha_creacion.strftime("%d/%m/%Y")
                    writer.writerow([
                        cuenta.numero_cuenta, cuenta.saldo, estado, 
                        fecha_creacion, cuenta.retiros_diarios
                    ])
            
            print(f"Cuentas exportadas a: {archivo}")
            
        except ImportError:
            print("Módulo CSV no disponible")
        except IOError as e:
            print(f"Error exportando datos: {e}")
    
    def generar_reporte_completo(self):
        """Genera un reporte completo del sistema"""
        try:
            fecha = datetime.now()
            archivo = f"reporte_completo_{fecha.strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(archivo, 'w', encoding='utf-8') as f:
                f.write("="*60 + "\n")
                f.write("REPORTE COMPLETO DEL SISTEMA ATM\n")
                f.write("="*60 + "\n")
                f.write(f"Fecha del reporte: {fecha.strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                
                # Estadísticas generales
                f.write("ESTADÍSTICAS GENERALES\n")
                f.write("-"*30 + "\n")
                f.write(f"Total de cuentas: {len(self.cajero.cuentas)}\n")
                f.write(f"Cuentas activas: {sum(1 for c in self.cajero.cuentas.values() if not c.bloqueada)}\n")
                f.write(f"Cuentas bloqueadas: {sum(1 for c in self.cajero.cuentas.values() if c.bloqueada)}\n")
                f.write(f"Saldo total: ${sum(c.saldo for c in self.cajero.cuentas.values()):,.2f}\n")
                f.write(f"Total de transacciones: {len(self.cajero.transacciones)}\n\n")
                
                # Información de cuentas
                f.write("DETALLE DE CUENTAS\n")
                f.write("-"*30 + "\n")
                for cuenta in self.cajero.cuentas.values():
                    estado = "BLOQUEADA" if cuenta.bloqueada else "ACTIVA"
                    f.write(f"Cuenta: {cuenta.numero_cuenta}\n")
                    f.write(f"  Saldo: ${cuenta.saldo:,.2f}\n")
                    f.write(f"  Estado: {estado}\n")
                    f.write(f"  Fecha creación: {cuenta.fecha_creacion.strftime('%d/%m/%Y')}\n")
                    f.write(f"  Retiros diarios: ${cuenta.retiros_diarios:,.2f}\n\n")
                
                # Últimas transacciones
                f.write("ÚLTIMAS 20 TRANSACCIONES\n")
                f.write("-"*30 + "\n")
                ultimas = self.cajero.transacciones[-20:] if self.cajero.transacciones else []
                for trans in reversed(ultimas):
                    f.write(f"{trans}\n")
            
            print(f"Reporte completo generado: {archivo}")
            
        except IOError as e:
            print(f"Error generando reporte: {e}")
    
    def menu_admin(self):
        """Menú principal del administrador"""
        opciones = [
            "Ver estadísticas del sistema",
            "Ver registro de transacciones", 
            "Gestionar cuentas",
            "Limpiar registro de transacciones",
            "Exportar datos",
            "Salir del modo administrador"
        ]
        
        while True:
            opcion = InterfazUsuario.mostrar_menu("PANEL DE ADMINISTRADOR", opciones)
            
            if opcion == "1":
                self.ver_estadisticas()
            elif opcion == "2":
                self.ver_logs_transacciones()
            elif opcion == "3":
                self.gestionar_cuentas()
            elif opcion == "4":
                self.limpiar_logs()
            elif opcion == "5":
                self.exportar_datos()
            elif opcion == "6":
                break
            
            input("\nPresione Enter para continuar...")

def main():
    """Función principal del programa"""
    print("Iniciando Sistema de Cajero Automático...")
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(ConfiguracionATM.ARCHIVO_LOGS, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    cajero = CajeroAutomatico()
    admin = AdministradorATM(cajero)
    
    opciones_principales = [
        "Acceso de usuario",
        "Acceso de administrador", 
        "Salir del sistema"
    ]
    
    try:
        while True:
            opcion = InterfazUsuario.mostrar_menu("SISTEMA CAJERO AUTOMÁTICO", opciones_principales)
            
            if opcion == "1":
                if cajero.autenticar_usuario():
                    cajero.menu_usuario()
            elif opcion == "2":
                if admin.autenticar_admin():
                    admin.menu_admin()
            elif opcion == "3":
                if InterfazUsuario.confirmar_operacion("¿Desea salir del sistema?"):
                    print("\nCerrando sistema de cajero automático...")
                    print("¡Gracias por usar nuestros servicios!")
                    break
            
            # Pequeña pausa antes de mostrar el menú principal nuevamente
            if opcion in ["1", "2"]:
                input("\nPresione Enter para volver al menú principal...")
    
    except KeyboardInterrupt:
        print("\n\nSistema interrumpido por el usuario")
        print("Guardando datos...")
        cajero.guardar_datos()
        print("Datos guardados. Sistema cerrado de forma segura.")
    
    except Exception as e:
        print(f"\nError inesperado: {e}")
        logging.error(f"Error inesperado en main: {e}")
        print("Intentando guardar datos...")
        try:
            cajero.guardar_datos()
            print("Datos guardados.")
        except:
            print("No se pudieron guardar los datos.")

if __name__ == "__main__":
    main()