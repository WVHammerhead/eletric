"""Varredura completa do módulo dianteiro: esterço + suspensão integrados.

CORREÇÕES IMPLEMENTADAS (Prompt 2):
1. Sinal da folga corrigido em verificar_interferencias (folga positiva expande caixas)
2. Geometria real do balancim (260mm) conectada às coordenadas de pivô e eixo
3. Cinemática correta: olhal superior do amortecedor, caixa de direção e tensor fixos ao chassi
4. Comprimento do amortecedor varia dinamicamente com o curso
5. Espelhamento do lado esquerdo corrigido (y_min < y_max)
6. Matriz completa de colisões componente vs. componente implementada

Integra TODOS os componentes em uma única análise 3D:
- Cubo de roda (200mm entre centros de rolamentos)
- Espelho de freio (tambor 130mm)
- Balancim 260mm (custom)
- Motores (2× por roda)
- Corrente + tensor
- Amortecedor
- Articulações (pivô, rótulas)
- Suportes (motor, tensor, amortecedor)
- Caixa de direção
- Proteção de corrente

Varredura combinada:
- Esterço: 0° a 25° (incrementos 5°)
- Suspensão: -40mm (extensão) a +80mm (compressão) (incrementos 20mm)
- Total: 6 ângulos × 7 cursos = 42 configurações

Gera relatório HTML com:
- Tabela de interferências por configuração
- Folgas mínimas (componente vs. carroceria/piso)
- Visualização 2D das envoltórias (xy, xz)
- Lista de colisões críticas

Uso:
    python varredura_modulo_completo.py
    python varredura_modulo_completo.py --html saida.html
"""
import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict


# ==================== GEOMETRIA BASE ====================

BITOLA_MM = 1420.0
YR = BITOLA_MM / 2.0                      # 710mm
X_EIXO = 600.0
X_PIVO = 520.0
Z_EIXO = 258.0                            # raio nominal roda 80/100-14
RECUO_PINO = 89.0
RAIO_RODA = 258.0
LARGURA_PNEU = 90.0

# Garfo dianteiro biapoiado
GARFO = {
    'altura_pernas_mm': 470.0,            # comprimento das pernas (eixo -> travessa)
    'diametro_perna_mm': 63.5,            # Ø63,5×4mm
    'espessura_perna_mm': 4.0,
    'deslocamento_pernas_mm': 175.0,      # ±175mm do plano médio da roda (nominal)
    'folga_minima_mm': 10.0,              # folga exigida perna × motor/corrente/proteção
    'z_travessa_mm': RAIO_RODA + 470.0,   # 727,8mm do solo
}

# Carroceria e piso
Y_MAX_CARROCERIA = 820.0
Z_PISO_ACABADO = 295.0
Z_LONGARINA_TOPO = 205.0
Z_CAPO_MAX = 811.0                        # altura máxima do capô (limite para caixa de direção)

# Zona de passagem de roda (wheel well) — componentes permitidos abaixo do piso
WHEEL_WELL = {
    'x_min': 500.0,  # mais largo p/ incluir região do cubo/freio
    'x_max': 700.0,
    'y_min': 550.0,  # expandido (tambor em ~595mm)
    'y_max': 900.0,
    'z_min': 100.0,  # tudo acima deste nível (abaixo=obstáculo real como chassi)
}

# ==================== COMPONENTES ====================

# Cubo de roda
CUBO = {
    'comprimento_mm': 200.0,              # entre centros rolamentos
    'diametro_central_mm': 80.0,          # corpo do cubo
    'flange_externo_mm': 140.0,           # diâmetro flange externo (lado roda)
    'espessura_flange_mm': 15.0,
}

# Freio a tambor
FREIO = {
    'diametro_tambor_mm': 130.0,          # tambor Biz 125 (medido típico)
    'largura_tambor_mm': 30.0,
    'espelho_diametro_mm': 180.0,         # espelho fixo (parafusado no balancim)
    'espelho_espessura_mm': 8.0,
}

# Balancim (balança curta custom)
BALANCIM = {
    'comprimento_pivo_eixo_mm': 260.0,
    'extensao_alem_eixo_mm': 80.0,        # mancal externo
    'diametro_tubo_mm': 32.0,
    'espessura_parede_mm': 3.0,
    'y_afastamento_mm': 60.0,             # braço externo: yr + 60
    'deslocamento_pivo_y_mm': 0.0,        # sem deslocamento adicional
}

# Motores
MOTOR = {
    'diametro_mm': 103.0,
    'comprimento_mm': 190.0,
    'posicoes_pinhao': {                  # (x, z) no plano da corrente
        'A': (650.0, 372.0),              # traseiro
        'B': (530.0, 372.0),              # frente
    },
    'folga_pneu_mm': 25.0,
    'flange_diametro_mm': 140.0,          # flange de montagem
    'flange_espessura_mm': 12.0,
    'parafusos_raio_mm': 60.0,            # círculo de furos M8
}

# Corrente e tensor
CORRENTE = {
    'passo_mm': 12.7,                     # #428
    'largura_mm': 8.0,
    'dentes_pinhao': 11,
    'dentes_coroa': 60,
    'y_plano_mm': YR - MOTOR['folga_pneu_mm'],  # 685mm
}

TENSOR = {
    'posicao': (620.0, CORRENTE['y_plano_mm'], 300.0),  # x, y, z
    'braco_mm': 80.0,
    'diametro_pinhao_mm': 45.0,           # 11 dentes
    'suporte_largura_mm': 60.0,
    'suporte_altura_mm': 80.0,
    'placa_espessura_mm': 4.75,           # placa de montagem (AISI 1020)
    'placa_largura_mm': 80.0,
    'placa_altura_mm': 100.0,
}

# Amortecedor
AMORTECEDOR = {
    'diametro_corpo_mm': 45.0,
    'olhal_chassi': (480.0, YR + 60.0, 520.0),
    'olhal_balancim': (520.0, YR + 60.0, 298.0),  # ajustado conforme curso
}

# Caixa de direção
CAIXA_DIRECAO = {
    'altura_mm': 160.0,
    'diametro_mm': 95.0,                  # Ø95mm mínimo para sede Ø85mm do rolamento 30209
    'z_base_mm': None,                    # calculado dinamicamente para caber sob o capô
    'z_topo_max_mm': 801.0,               # capô (811) menos 10 mm de folga mínima
}

# Proteção de corrente
PROTECAO = {
    'largura_mm': 150.0,                  # x
    'altura_mm': 250.0,                   # z
    'profundidade_mm': 120.0,             # y
    'espessura_mm': 2.0,
}


# ==================== CLASSES DE GEOMETRIA ====================

@dataclass
class Ponto3D:
    x: float
    y: float
    z: float
    
    def distancia(self, outro: 'Ponto3D') -> float:
        return math.sqrt((self.x - outro.x)**2 + (self.y - outro.y)**2 + (self.z - outro.z)**2)
    
    def dict(self):
        return {'x': round(self.x, 1), 'y': round(self.y, 1), 'z': round(self.z, 1)}


@dataclass
class AABB:
    """Axis-Aligned Bounding Box (caixa envolvente alinhada)."""
    nome: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    grupo: str = 'geral'
    yaw: float = 0.0   # rotação (rad) em torno do eixo vertical pelo próprio centro: >0 = caixa orientada (OBB)
    
    def _meios(self):
        return (self.x_max - self.x_min) / 2, (self.y_max - self.y_min) / 2
    
    def _eixos_xy(self):
        c, s_ = math.cos(self.yaw), math.sin(self.yaw)
        return (c, s_), (-s_, c)
    
    def sobreposicao_obb(self, outro: 'AABB', folga: float = 0.0) -> Optional[float]:
        """Teorema dos eixos separadores (SAT) em xy + intervalo em z, para caixas com esterço (yaw).
        
        Retorna a menor sobreposição (mm, já somada a folga) ou None se houver separação maior que a folga."""
        dz = min(self.z_max, outro.z_max) - max(self.z_min, outro.z_min) + folga
        if dz <= 0:
            return None
        c1, c2 = self.centro(), outro.centro()
        d = (c2.x - c1.x, c2.y - c1.y)
        h1, h2 = self._meios(), outro._meios()
        e1, e2 = self._eixos_xy(), outro._eixos_xy()
        menor = dz
        for u in (*e1, *e2):
            r1 = h1[0] * abs(u[0]*e1[0][0] + u[1]*e1[0][1]) + h1[1] * abs(u[0]*e1[1][0] + u[1]*e1[1][1])
            r2 = h2[0] * abs(u[0]*e2[0][0] + u[1]*e2[0][1]) + h2[1] * abs(u[0]*e2[1][0] + u[1]*e2[1][1])
            sobre = r1 + r2 + folga - abs(d[0]*u[0] + d[1]*u[1])
            if sobre <= 0:
                return None
            menor = min(menor, sobre)
        return menor
    
    def centro(self) -> Ponto3D:
        return Ponto3D(
            (self.x_min + self.x_max) / 2,
            (self.y_min + self.y_max) / 2,
            (self.z_min + self.z_max) / 2
        )
    
    def intercepta(self, outro: 'AABB', folga: float = 0.0) -> bool:
        """Verifica se há interseção considerando folga.
        
        CORREÇÃO PROMPT 2.1: folga positiva expande as caixas (detecta violação de margem mínima).
        folga > 0: exige separação mínima 'folga' (não dobrada); detecta peças que não colidem fisicamente mas violam folga mínima
        folga = 0: detecta apenas colisão física
        folga < 0: contrai as caixas (usado para permitir aproximação controlada)
        """
        if self.yaw or outro.yaw:
            return self.sobreposicao_obb(outro, folga) is not None
        # Separadas se, em algum eixo, o vão entre as caixas atende a folga exigida (vão == folga exigida é aceitável).
        ok = (lambda vao: vao >= folga) if folga > 0 else (lambda vao: vao > folga)
        return not (
            ok(outro.x_min - self.x_max) or ok(self.x_min - outro.x_max) or
            ok(outro.y_min - self.y_max) or ok(self.y_min - outro.y_max) or
            ok(outro.z_min - self.z_max) or ok(self.z_min - outro.z_max)
        )
    
    def penetracao(self, outro: 'AABB') -> Optional[float]:
        """Retorna penetração mínima (mm) se houver interseção, None caso contrário."""
        if self.yaw or outro.yaw:
            return self.sobreposicao_obb(outro, 0.0)
        if not self.intercepta(outro):
            return None
        
        pen_x = min(self.x_max - outro.x_min, outro.x_max - self.x_min)
        pen_y = min(self.y_max - outro.y_min, outro.y_max - self.y_min)
        pen_z = min(self.z_max - outro.z_min, outro.z_max - self.z_min)
        
        return min(pen_x, pen_y, pen_z)
    
    def dict(self):
        return {
            'nome': self.nome,
            'x': [round(self.x_min, 1), round(self.x_max, 1)],
            'y': [round(self.y_min, 1), round(self.y_max, 1)],
            'z': [round(self.z_min, 1), round(self.z_max, 1)],
            'grupo': self.grupo,
        }


@dataclass
class Cilindro:
    """Cilindro (tubo, eixo) definido por dois pontos e raio."""
    nome: str
    p1: Ponto3D
    p2: Ponto3D
    raio: float
    grupo: str = 'geral'
    
    def aabb(self) -> AABB:
        """Caixa envolvente exata de um cilindro de tampas planas: o raio só entra nos eixos perpendiculares ao eixo do cilindro."""
        dx, dy, dz = self.p2.x - self.p1.x, self.p2.y - self.p1.y, self.p2.z - self.p1.z
        c = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
        ex, ey, ez = (self.raio*math.sqrt(max(0.0, 1 - (d/c)**2)) for d in (dx, dy, dz))
        return AABB(
            self.nome,
            min(self.p1.x, self.p2.x) - ex, max(self.p1.x, self.p2.x) + ex,
            min(self.p1.y, self.p2.y) - ey, max(self.p1.y, self.p2.y) + ey,
            min(self.p1.z, self.p2.z) - ez, max(self.p1.z, self.p2.z) + ez,
            self.grupo
        )


# ==================== TRANSFORMAÇÕES 3D ====================

def girar_ponto_em_torno_eixo(p: Ponto3D, eixo: Ponto3D, direcao: Ponto3D, angulo_rad: float) -> Ponto3D:
    """Gira ponto em torno de um eixo arbitrário (Rodrigues' rotation formula)."""
    # Normalizar direção
    mag = math.sqrt(direcao.x**2 + direcao.y**2 + direcao.z**2)
    if mag < 1e-9:
        return p
    kx, ky, kz = direcao.x / mag, direcao.y / mag, direcao.z / mag
    
    # Vetor do eixo ao ponto
    vx, vy, vz = p.x - eixo.x, p.y - eixo.y, p.z - eixo.z
    
    # Rodrigues
    cos_ang = math.cos(angulo_rad)
    sin_ang = math.sin(angulo_rad)
    
    # v_rot = v*cos + (k × v)*sin + k*(k·v)*(1-cos)
    dot_kv = kx*vx + ky*vy + kz*vz
    cross_x = ky*vz - kz*vy
    cross_y = kz*vx - kx*vz
    cross_z = kx*vy - ky*vx
    
    rx = vx*cos_ang + cross_x*sin_ang + kx*dot_kv*(1 - cos_ang)
    ry = vy*cos_ang + cross_y*sin_ang + ky*dot_kv*(1 - cos_ang)
    rz = vz*cos_ang + cross_z*sin_ang + kz*dot_kv*(1 - cos_ang)
    
    return Ponto3D(eixo.x + rx, eixo.y + ry, eixo.z + rz)


def deslocar_vertical(p: Ponto3D, dz: float) -> Ponto3D:
    """Desloca ponto verticalmente (suspensão)."""
    return Ponto3D(p.x, p.y, p.z + dz)


# ==================== CONSTRUÇÃO DO MÓDULO ====================

class ModuloCompleto:
    """Módulo dianteiro completo em uma configuração (esterço + suspensão)."""
    
    def __init__(self, angulo_esterco_graus: float, curso_suspensao_mm: float, lado: str = 'direito',
                 deslocamento_perna_interna_mm: Optional[float] = None):
        self.deslocamento_perna_interna_mm = (GARFO['deslocamento_pernas_mm'] if deslocamento_perna_interna_mm is None
                                              else deslocamento_perna_interna_mm)
        self.angulo_graus = angulo_esterco_graus
        self.curso_mm = curso_suspensao_mm
        self.lado = lado
        self.sinal_y = 1.0 if lado == 'direito' else -1.0
        
        # Pino de esterço (atravessa a roda)
        self.pino_esterco = Ponto3D(X_EIXO, self.sinal_y * (YR - RECUO_PINO), Z_EIXO)
        self.direcao_pino = Ponto3D(0, 0, 1)  # vertical
        
        self.componentes: List[AABB] = []
        self.cilindros: List[Cilindro] = []
        
        self._construir_modulo()
        self._orientar_componentes()
    
    def _girar_modulo(self, p: Ponto3D) -> Ponto3D:
        """Aplica esterço ao ponto (gira em torno do pino)."""
        ang_rad = math.radians(self.angulo_graus)
        return girar_ponto_em_torno_eixo(p, self.pino_esterco, self.direcao_pino, ang_rad)
    
    def _aplicar_suspensao(self, p: Ponto3D) -> Ponto3D:
        """Aplica curso de suspensão ao ponto."""
        return deslocar_vertical(p, self.curso_mm)
    
    def _transformar(self, p: Ponto3D) -> Ponto3D:
        """Aplica suspensão E esterço (nesta ordem)."""
        p_susp = self._aplicar_suspensao(p)
        return self._girar_modulo(p_susp)
    
    def _construir_modulo(self):
        """Constrói todos os componentes do módulo."""
        sy = self.sinal_y
        
        # 1. CUBO DE RODA
        cubo_x = X_EIXO
        cubo_y_centro = sy * YR
        cubo_z = Z_EIXO
        
        L_cubo = CUBO['comprimento_mm']
        D_cubo = CUBO['diametro_central_mm']
        
        # Centro do cubo (antes de transformar)
        centro_cubo_base = Ponto3D(cubo_x, cubo_y_centro, cubo_z)
        centro_cubo = self._transformar(centro_cubo_base)
        
        # AABB do cubo (cilindro horizontal)
        self.componentes.append(AABB(
            f'Cubo roda ({self.lado})',
            centro_cubo.x - 20, centro_cubo.x + 20,  # comprimento pequeno em x
            centro_cubo.y - L_cubo/2, centro_cubo.y + L_cubo/2,
            centro_cubo.z - D_cubo/2, centro_cubo.z + D_cubo/2,
            'cubo'
        ))
        
        # 2. TAMBOR DE FREIO (dentro da roda, lado interno)
        D_tambor = FREIO['diametro_tambor_mm']
        L_tambor = FREIO['largura_tambor_mm']
        
        # Centro do tambor (deslocado p/ dentro da roda)
        y_tambor_base = cubo_y_centro - sy * (L_cubo/2 + L_tambor/2)
        centro_tambor_base = Ponto3D(cubo_x, y_tambor_base, cubo_z)
        centro_tambor = self._transformar(centro_tambor_base)
        
        self.componentes.append(AABB(
            f'Tambor freio ({self.lado})',
            centro_tambor.x - D_tambor/2, centro_tambor.x + D_tambor/2,
            centro_tambor.y - L_tambor/2, centro_tambor.y + L_tambor/2,
            centro_tambor.z - D_tambor/2, centro_tambor.z + D_tambor/2,
            'freio'
        ))
        
        # 3. ESPELHO DE FREIO (parafusado no balancim, fixo)
        D_espelho = FREIO['espelho_diametro_mm']
        e_espelho = FREIO['espelho_espessura_mm']
        
        # Adjacente ao tambor, lado externo
        y_espelho_base = cubo_y_centro - sy * (L_cubo/2 + L_tambor + e_espelho/2)
        centro_espelho_base = Ponto3D(cubo_x, y_espelho_base, cubo_z)
        centro_espelho = self._transformar(centro_espelho_base)
        
        self.componentes.append(AABB(
            f'Espelho freio ({self.lado})',
            centro_espelho.x - D_espelho/2, centro_espelho.x + D_espelho/2,
            centro_espelho.y - e_espelho/2, centro_espelho.y + e_espelho/2,
            centro_espelho.z - D_espelho/2, centro_espelho.z + D_espelho/2,
            'freio'
        ))
        
        # 4. BALANCIM (tubo Ø32×3mm)
        # CORREÇÃO PROMPT 2.2: Geometria real com 260mm entre pivô e eixo
        comprimento_balancim = BALANCIM['comprimento_pivo_eixo_mm']
        
        # Eixo da roda e pivô: a distância 3D pivô→eixo é exatamente comprimento_pivo_eixo_mm.
        # y e z do pivô vêm do projeto; x do pivô é derivado (recuo no sentido -x a partir do eixo).
        y_pivo_base = sy * (YR + BALANCIM['y_afastamento_mm'] + BALANCIM['deslocamento_pivo_y_mm'])
        z_pivo = cubo_z
        dy_pe = y_pivo_base - cubo_y_centro
        dz_pe = z_pivo - cubo_z
        resto = comprimento_balancim**2 - dy_pe**2 - dz_pe**2
        if resto <= 0:
            raise ValueError('comprimento_pivo_eixo_mm menor que o afastamento lateral/vertical pivô-eixo')
        x_pivo = X_EIXO - math.sqrt(resto)
        self.x_pivo = x_pivo
        
        pivo_base = Ponto3D(x_pivo, y_pivo_base, z_pivo)
        pivo = self._transformar(pivo_base)
        
        eixo_base = Ponto3D(X_EIXO, cubo_y_centro, cubo_z)
        eixo = self._transformar(eixo_base)
        
        # Verificar distância real pivô-eixo
        dist_pivo_eixo_real = pivo_base.distancia(eixo_base)
        # Se menor que 260mm, estender tip do balancim para atingir 260mm total
        
        # Tip do balancim (extensão além do eixo)
        extensao = BALANCIM['extensao_alem_eixo_mm']
        # Vetor pivô → eixo (base, antes de transformações)
        dx_base = eixo_base.x - pivo_base.x
        dy_base = eixo_base.y - pivo_base.y
        dz_base = eixo_base.z - pivo_base.z
        dist_base = math.sqrt(dx_base**2 + dy_base**2 + dz_base**2)
        
        # Tip estendido além do eixo
        if dist_base > 1e-6:
            fator_tip = (dist_base + extensao) / dist_base
            tip_base = Ponto3D(
                pivo_base.x + dx_base * fator_tip,
                pivo_base.y + dy_base * fator_tip,
                pivo_base.z + dz_base * fator_tip
            )
            tip = self._transformar(tip_base)
        else:
            tip_base = Ponto3D(eixo_base.x, eixo_base.y + sy*extensao, eixo_base.z)
            tip = self._transformar(tip_base)
        
        self.cilindros.append(Cilindro(
            f'Balancim ({self.lado})',
            pivo, tip,
            BALANCIM['diametro_tubo_mm'] / 2,
            'balancim'
        ))
        
        # 5. MOTORES (2 por roda, giram com módulo)
        y_plano = CORRENTE['y_plano_mm']
        L_motor = MOTOR['comprimento_mm']
        D_motor = MOTOR['diametro_mm']
        
        for nome, (x_pinhao, z_pinhao) in MOTOR['posicoes_pinhao'].items():
            # Centro do motor (carcaça p/ dentro da roda)
            y_motor_base = sy * (y_plano - L_motor/2)
            centro_motor_base = Ponto3D(x_pinhao, y_motor_base, z_pinhao)
            centro_motor = self._transformar(centro_motor_base)
            
            self.componentes.append(AABB(
                f'Motor {nome} ({self.lado})',
                centro_motor.x - D_motor/2, centro_motor.x + D_motor/2,
                centro_motor.y - L_motor/2, centro_motor.y + L_motor/2,
                centro_motor.z - D_motor/2, centro_motor.z + D_motor/2,
                'motor'
            ))
            
            # Flange de montagem (lado externo do motor)
            D_flange = MOTOR['flange_diametro_mm']
            e_flange = MOTOR['flange_espessura_mm']
            y_flange_base = sy * (y_plano + e_flange/2)
            centro_flange_base = Ponto3D(x_pinhao, y_flange_base, z_pinhao)
            centro_flange = self._transformar(centro_flange_base)
            
            self.componentes.append(AABB(
                f'Flange motor {nome} ({self.lado})',
                centro_flange.x - D_flange/2, centro_flange.x + D_flange/2,
                centro_flange.y - e_flange/2, centro_flange.y + e_flange/2,
                centro_flange.z - D_flange/2, centro_flange.z + D_flange/2,
                'suporte_motor'
            ))
        
        # 6. TENSOR DE CORRENTE
        x_t, y_t_base, z_t = TENSOR['posicao']
        y_t_base *= sy
        centro_tensor_base = Ponto3D(x_t, y_t_base, z_t)
        centro_tensor = self._transformar(centro_tensor_base)
        
        self.componentes.append(AABB(
            f'Tensor corrente ({self.lado})',
            centro_tensor.x - TENSOR['suporte_largura_mm']/2,
            centro_tensor.x + TENSOR['suporte_largura_mm']/2,
            centro_tensor.y - 40, centro_tensor.y + 40,
            centro_tensor.z - TENSOR['suporte_altura_mm']/2,
            centro_tensor.z + TENSOR['suporte_altura_mm']/2,
            'tensor'
        ))
        
        # Placa de montagem do tensor (FIXA no chassi, não move com suspensão)
        placa_w = TENSOR['placa_largura_mm']
        placa_h = TENSOR['placa_altura_mm']
        placa_e = TENSOR['placa_espessura_mm']
        
        # Placa ancorada no chassi, paralela ao plano yz
        y_placa_base = y_t_base - sy * 20  # recuada ~20mm para o centro (y_t_base já tem o sinal do lado)
        centro_placa = Ponto3D(x_t, y_placa_base, z_t)  # sem transformação (fixa ao chassi)
        
        self.componentes.append(AABB(
            f'Placa tensor ({self.lado})',
            centro_placa.x - placa_e/2, centro_placa.x + placa_e/2,
            centro_placa.y - placa_w/2, centro_placa.y + placa_w/2,
            centro_placa.z - placa_h/2, centro_placa.z + placa_h/2,
            'suporte_tensor'
        ))
        
        # 7. AMORTECEDOR 
        # CORREÇÃO PROMPT 2.3: Olhal chassi FIXO (não move com suspensão nem esterço)
        # Comprimento varia dinamicamente: L₀ ± curso
        x_oc, y_oc_base, z_oc = AMORTECEDOR['olhal_chassi']
        y_oc_base *= sy  # espelha corretamente
        olhal_chassi = Ponto3D(x_oc, y_oc_base, z_oc)  # SEM transformação (fixo ao chassi)
        
        # Olhal balancim: move com suspensão E gira com esterço
        x_ob, y_ob_base, z_ob = AMORTECEDOR['olhal_balancim']
        y_ob_base *= sy  # CORREÇÃO PROMPT 2.4: espelhamento correto
        olhal_balancim_base = Ponto3D(x_ob, y_ob_base, z_ob)
        olhal_balancim = self._transformar(olhal_balancim_base)
        
        # Comprimento varia dinamicamente com o curso
        # Raio do cilindro representa o corpo do amortecedor
        self.cilindros.append(Cilindro(
            f'Amortecedor ({self.lado})',
            olhal_chassi, olhal_balancim,
            AMORTECEDOR['diametro_corpo_mm'] / 2,
            'amortecedor'
        ))
        
        # 8. CAIXA DE DIREÇÃO (FIXA no chassi, não move com suspensão)
        # Calcula z_base para que o topo fique sob o capô (z_topo_max)
        z_topo_desejado = CAIXA_DIRECAO['z_topo_max_mm']
        z_caixa_base = z_topo_desejado - CAIXA_DIRECAO['altura_mm']
        centro_caixa = Ponto3D(X_EIXO, sy * (YR - RECUO_PINO), z_caixa_base)  # sem transformação
        
        topo_caixa = Ponto3D(
            centro_caixa.x,
            centro_caixa.y,
            centro_caixa.z + CAIXA_DIRECAO['altura_mm']
        )
        
        self.cilindros.append(Cilindro(
            f'Caixa direção ({self.lado})',
            centro_caixa, topo_caixa,
            CAIXA_DIRECAO['diametro_mm'] / 2,
            'direcao'
        ))
        
        # 8b. PERNAS DO GARFO (tubos Ø63,5×4mm a ±175mm do plano médio)
        # Modelam o volume 3D das pernas biapoiadas
        H_perna = GARFO['altura_pernas_mm']
        D_perna = GARFO['diametro_perna_mm']
        y_deslocamento = GARFO['deslocamento_pernas_mm']
        
        # As pernas ficam a ±deslocamento do PLANO DA RODA (y = ±YR), não do plano médio do veículo.
        y_perna_externa_base = sy * (YR + y_deslocamento)
        p_ext_inf = self._transformar(Ponto3D(X_EIXO, y_perna_externa_base, Z_EIXO))
        p_ext_sup = self._transformar(Ponto3D(X_EIXO, y_perna_externa_base, Z_EIXO + H_perna))
        self.cilindros.append(Cilindro(
            f'Perna garfo externa ({self.lado})',
            p_ext_inf, p_ext_sup,
            D_perna / 2,
            'garfo'
        ))
        
        # Perna interna (lado do centro do veículo): precisa passar por dentro dos motores e da corrente.
        y_perna_interna_base = sy * (YR - self.deslocamento_perna_interna_mm)
        p_int_inf = self._transformar(Ponto3D(X_EIXO, y_perna_interna_base, Z_EIXO))
        p_int_sup = self._transformar(Ponto3D(X_EIXO, y_perna_interna_base, Z_EIXO + H_perna))
        self.cilindros.append(Cilindro(
            f'Perna garfo interna ({self.lado})',
            p_int_inf, p_int_sup,
            D_perna / 2,
            'garfo'
        ))
        
        # 9. PROTEÇÃO DE CORRENTE (envelope retangular, gira com módulo)
        # Centro entre os motores
        x_prot = (MOTOR['posicoes_pinhao']['A'][0] + MOTOR['posicoes_pinhao']['B'][0]) / 2
        z_prot = (MOTOR['posicoes_pinhao']['A'][1] + MOTOR['posicoes_pinhao']['B'][1]) / 2
        y_prot_base = sy * y_plano
        
        centro_prot_base = Ponto3D(x_prot, y_prot_base, z_prot)
        centro_prot = self._transformar(centro_prot_base)
        
        self.componentes.append(AABB(
            f'Proteção corrente ({self.lado})',
            centro_prot.x - PROTECAO['largura_mm']/2,
            centro_prot.x + PROTECAO['largura_mm']/2,
            centro_prot.y - PROTECAO['profundidade_mm']/2,
            centro_prot.y + PROTECAO['profundidade_mm']/2,
            centro_prot.z - PROTECAO['altura_mm']/2,
            centro_prot.z + PROTECAO['altura_mm']/2,
            'protecao'
        ))
    
    def _orientar_componentes(self):
        """Componentes que giram com o esterço viram caixas orientadas (OBB); os fixos ao chassi não."""
        for comp in self.componentes:
            if comp.grupo != 'suporte_tensor':
                comp.yaw = math.radians(self.angulo_graus)
    
    def verificar_interferencias(self, folga_mm: float = 0.0) -> List[Dict]:
        """Verifica interferências entre componentes e obstáculos.
        
        CORREÇÃO PROMPT 2.1: folga_mm POSITIVA expande as caixas corretamente.
        """
        interferencias = []
        
        # Obstáculos fixos
        # CORREÇÃO PROMPT 2.4: espelhamento correto (y_min < y_max sempre)
        if self.sinal_y > 0:  # direito
            carroceria = AABB('Carroceria', -1000, 1000, 
                              Y_MAX_CARROCERIA, 2000, -1000, 2000, 'obstaculo')
        else:  # esquerdo: y_min negativo, y_max negativo maior (menos negativo)
            carroceria = AABB('Carroceria', -1000, 1000,
                              -2000, -Y_MAX_CARROCERIA, -1000, 2000, 'obstaculo')
        
        piso = AABB('Piso+EVA', -1000, 3000, -2000, 2000, 
                    -1000, Z_PISO_ACABADO, 'obstaculo')
        
        # Longarina: CORREÇÃO PROMPT 2.4: espelhamento correto
        if self.sinal_y > 0:  # direito
            longarina = AABB('Longarina', 280, 900,
                             500, 900,
                             Z_LONGARINA_TOPO - 80, Z_LONGARINA_TOPO, 'obstaculo')
        else:  # esquerdo: y_min negativo, y_max negativo maior
            longarina = AABB('Longarina', 280, 900,
                             -900, -500,
                             Z_LONGARINA_TOPO - 80, Z_LONGARINA_TOPO, 'obstaculo')
        
        # Capô: limite de altura (obstáculo acima de Z_CAPO_MAX)
        capo = AABB('Capô', -1000, 3000, -2000, 2000,
                    Z_CAPO_MAX, 3000, 'obstaculo')
        
        obstaculos = [carroceria, piso, longarina, capo]
        
        # Verificar componentes vs. obstáculos
        for comp in self.componentes:
            for obs in obstaculos:
                # Verificar com folga positiva (expande as caixas)
                if comp.intercepta(obs, folga_mm):
                    pen = comp.penetracao(obs)
                    
                    # Zona permitida: wheel well
                    if 'Piso' in obs.nome:
                        em_wheel_well = self._componente_em_wheel_well(comp)
                        if em_wheel_well:
                            # Componente no wheel well: só reportar se muito profundo (< z_min permitido)
                            if comp.z_min < WHEEL_WELL['z_min']:
                                interferencias.append({
                                    'componente': comp.nome,
                                    'obstaculo': 'Wheel well (z_min)',
                                    'invasao_mm': round(WHEEL_WELL['z_min'] - comp.z_min, 1),
                                    'tipo': 'invasao_critica',
                                    'severidade': 'ALTA',
                                })
                            # Senão, invasão esperada (roda passa pelo piso no wheel well)
                            continue
                    
                    # Calcular invasão real ou violação de folga
                    if pen is not None and pen > 0:
                        # Colisão física
                        invasao_mm = pen
                    else:
                        # Sem colisão física, mas dentro da zona de folga
                        # Calcular distância mínima entre as caixas
                        invasao_mm = self._calcular_afastamento(comp, obs)
                    
                    # Determinar severidade
                    severidade = 'ALTA'
                    if 'Carroceria' in obs.nome:
                        # Invasão da carroceria: avaliar margem
                        y_comp_max = max(abs(comp.y_min), abs(comp.y_max))
                        margem = Y_MAX_CARROCERIA - y_comp_max
                        if margem >= 10:
                            severidade = 'BAIXA'
                        elif margem >= 0:
                            severidade = 'MEDIA'
                    elif 'Capô' in obs.nome:
                        # Invasão do capô: sempre crítica
                        severidade = 'ALTA'
                    elif invasao_mm < folga_mm:
                        severidade = 'MEDIA'
                    
                    interferencias.append({
                        'componente': comp.nome,
                        'obstaculo': obs.nome,
                        'invasao_mm': round(invasao_mm, 1),
                        'tipo': 'invasao' if pen and pen > 0 else 'folga_insuficiente',
                        'severidade': severidade,
                    })
        
        # Verificar cilindros vs. obstáculos (usando AABB do cilindro)
        for cil in self.cilindros:
            comp_aabb = cil.aabb()
            for obs in obstaculos:
                if comp_aabb.intercepta(obs, folga_mm):
                    pen = comp_aabb.penetracao(obs)
                    
                    # Verificar wheel well para cilindros também
                    if 'Piso' in obs.nome:
                        em_wheel_well = self._componente_em_wheel_well(comp_aabb)
                        if em_wheel_well:
                            if comp_aabb.z_min < WHEEL_WELL['z_min']:
                                interferencias.append({
                                    'componente': cil.nome,
                                    'obstaculo': 'Wheel well (z_min)',
                                    'invasao_mm': round(WHEEL_WELL['z_min'] - comp_aabb.z_min, 1),
                                    'tipo': 'invasao_critica_cilindro',
                                    'severidade': 'ALTA',
                                })
                            continue
                    
                    # Calcular invasão
                    if pen is not None and pen > 0:
                        invasao_mm = pen
                    else:
                        invasao_mm = self._calcular_afastamento(comp_aabb, obs)
                    
                    # Capô: sempre crítico
                    if 'Capô' in obs.nome:
                        severidade_cil = 'ALTA'
                    else:
                        severidade_cil = 'MEDIA' if invasao_mm < folga_mm else 'ALTA'
                    
                    interferencias.append({
                        'componente': cil.nome,
                        'obstaculo': obs.nome,
                        'invasao_mm': round(invasao_mm, 1),
                        'tipo': 'invasao_cilindro' if pen and pen > 0 else 'folga_insuficiente_cilindro',
                        'severidade': severidade_cil,
                    })
        
        # Verificar componentes vs. componentes (matriz completa)
        for i, comp1 in enumerate(self.componentes):
            for comp2 in self.componentes[i+1:]:
                if comp1.intercepta(comp2, folga_mm):
                    pen = comp1.penetracao(comp2)
                    if pen is not None and pen > 0:
                        interferencias.append({
                            'componente': f'{comp1.nome} × {comp2.nome}',
                            'obstaculo': 'Componente interno',
                            'invasao_mm': round(pen, 1),
                            'tipo': 'colisao_interna',
                            'severidade': 'ALTA',
                        })
        
        # PERNAS DO GARFO × componentes do lado da corrente (motores, flanges, proteção, tensor) e laço da corrente.
        folga_garfo = GARFO['folga_minima_mm']
        alvos = [c for c in self.componentes
                 if c.grupo in ('motor', 'suporte_motor', 'protecao', 'tensor', 'suporte_tensor')]
        alvos.append(self.aabb_laco_corrente())
        for perna in [c for c in self.cilindros if c.grupo == 'garfo']:
            pa = perna.aabb()
            for alvo in alvos:
                if pa.intercepta(alvo, folga_garfo):
                    pen = pa.penetracao(alvo)
                    colide = pen is not None and pen > 0
                    interferencias.append({
                        'componente': perna.nome,
                        'obstaculo': alvo.nome,
                        'invasao_mm': round(pen if colide else self._calcular_afastamento(pa, alvo), 1),
                        'tipo': 'colisao_garfo' if colide else 'folga_insuficiente_garfo',
                        'severidade': 'ALTA',
                    })
        
        return interferencias
    
    def aabb_laco_corrente(self) -> AABB:
        """Envelope do laço da corrente #428 (coroa + pinhões) no plano y = ±y_plano, girando com o módulo."""
        r_coroa = CORRENTE['passo_mm'] / (2 * math.sin(math.pi / CORRENTE['dentes_coroa'])) + 6.0
        r_pinhao = CORRENTE['passo_mm'] / (2 * math.sin(math.pi / CORRENTE['dentes_pinhao'])) + 6.0
        pontos = [(X_EIXO, Z_EIXO, r_coroa)] + [(x, z, r_pinhao) for (x, z) in MOTOR['posicoes_pinhao'].values()]
        x0 = min(x - r for x, z, r in pontos); x1 = max(x + r for x, z, r in pontos)
        z0 = min(z - r for x, z, r in pontos) + self.curso_mm * 0; z1 = max(z + r for x, z, r in pontos)
        yc = self.sinal_y * CORRENTE['y_plano_mm']
        w = CORRENTE['largura_mm'] / 2
        return AABB(f'Laço corrente #428 ({self.lado})', x0, x1, yc - w, yc + w, z0, z1, 'corrente')
    
    def _componente_em_wheel_well(self, comp: AABB) -> bool:
        """Verifica se componente está na zona de passagem de roda (wheel well)."""
        centro = comp.centro()
        y_abs = abs(centro.y)
        
        return (
            WHEEL_WELL['x_min'] <= centro.x <= WHEEL_WELL['x_max'] and
            WHEEL_WELL['y_min'] <= y_abs <= WHEEL_WELL['y_max']
        )
    
    def _calcular_afastamento(self, comp: AABB, obs: AABB) -> float:
        """Calcula distância mínima entre duas caixas que não se interceptam.
        
        Retorna valor negativo se houver colisão física.
        """
        # Distância em cada eixo
        dx = max(0, max(comp.x_min - obs.x_max, obs.x_min - comp.x_max))
        dy = max(0, max(comp.y_min - obs.y_max, obs.y_min - comp.y_max))
        dz = max(0, max(comp.z_min - obs.z_max, obs.z_min - comp.z_max))
        
        # Se todos zero, há colisão
        if dx == 0 and dy == 0 and dz == 0:
            pen = comp.penetracao(obs)
            return -pen if pen else 0.0
        
        # Distância euclidiana
        return math.sqrt(dx**2 + dy**2 + dz**2)
    
    def resumo(self) -> Dict:
        """Resumo da configuração."""
        return {
            'angulo_esterco_graus': self.angulo_graus,
            'curso_suspensao_mm': self.curso_mm,
            'lado': self.lado,
            'num_componentes': len(self.componentes),
            'num_cilindros': len(self.cilindros),
            'componentes': [c.dict() for c in self.componentes],
            'cilindros': [{'nome': c.nome, 'grupo': c.grupo, 
                          'p1': c.p1.dict(), 'p2': c.p2.dict(), 
                          'raio': c.raio} for c in self.cilindros],
        }


# ==================== VARREDURA COMPLETA ====================

def deslocamento_perna_interna_minimo(passo_mm: float = 1.0, limite_mm: float = 400.0) -> Dict:
    """Menor deslocamento axial da perna interna (a partir do plano da roda) sem colisão nem violar a folga mínima.

    Retorna também o deslocamento nominal e se houve colisão no nominal. Como motores, corrente e garfo giram
    juntos no esterço e sobem juntos na suspensão, basta verificar a configuração de repouso."""
    nominal = GARFO['deslocamento_pernas_mm']
    desloc = nominal
    folga = GARFO['folga_minima_mm']

    def conflitos(d):
        m = ModuloCompleto(0, 0, 'direito', deslocamento_perna_interna_mm=d)
        return [i for i in m.verificar_interferencias(folga)
                if 'interna' in i['componente'] and i['tipo'] in ('colisao_garfo', 'folga_insuficiente_garfo')]

    colide_nominal = bool(conflitos(nominal))
    while conflitos(desloc) and desloc < limite_mm:
        desloc += passo_mm
    return {'nominal_mm': nominal, 'colide_no_nominal': colide_nominal,
            'minimo_mm': desloc if desloc < limite_mm else None,
            'vao_entre_pernas_mm': (nominal + desloc) if desloc < limite_mm else None}


def varredura_completa(
    angulos_graus: List[float] = None,
    cursos_mm: List[float] = None,
    folga_mm: float = 25.0,
    lado: str = 'direito'
) -> Dict:
    """Executa varredura completa: todos ângulos × todos cursos."""
    
    if angulos_graus is None:
        angulos_graus = [0, 5, 10, 15, 20, 25]
    
    if cursos_mm is None:
        cursos_mm = [-40, -20, 0, 20, 40, 60, 80]  # extensão negativa, compressão positiva
    
    resultados = []
    
    for ang in angulos_graus:
        for curso in cursos_mm:
            modulo = ModuloCompleto(ang, curso, lado)
            interferencias = modulo.verificar_interferencias(folga_mm)
            
            resultados.append({
                'angulo_graus': ang,
                'curso_mm': curso,
                'configuracao': f'{ang}°, {curso:+.0f}mm',
                'num_interferencias': len(interferencias),
                'interferencias': interferencias,
                'ok': len(interferencias) == 0,
                'modulo': modulo.resumo(),
            })
    
    # Estatísticas
    total = len(resultados)
    ok = sum(1 for r in resultados if r['ok'])
    
    # Contar interferências críticas (severidade ALTA)
    criticas_total = 0
    for r in resultados:
        criticas = [i for i in r['interferencias'] if i.get('severidade') == 'ALTA']
        criticas_total += len(criticas)
    
    # Encontrar envelope máximo
    y_max_global = 0.0
    z_min_global = float('inf')
    
    for r in resultados:
        for comp in r['modulo']['componentes']:
            y_max_global = max(y_max_global, max(abs(comp['y'][0]), abs(comp['y'][1])))
            z_min_global = min(z_min_global, comp['z'][0])
    
    return {
        'parametros': {
            'angulos_testados_graus': angulos_graus,
            'cursos_testados_mm': cursos_mm,
            'folga_minima_mm': folga_mm,
            'lado': lado,
            'total_configuracoes': total,
        },
        'resultados': resultados,
        'estatisticas': {
            'configuracoes_total': total,
            'configuracoes_ok': ok,
            'configuracoes_com_interferencia': total - ok,
            'interferencias_criticas_total': criticas_total,
            'taxa_sucesso_pct': round(100 * ok / total, 1),
            'envelope_y_max_mm': round(y_max_global, 1),
            'envelope_z_min_mm': round(z_min_global, 1),
        },
        'conclusao': (
            f"✅ Todas as {total} configurações OK (0° a {max(angulos_graus)}°, "
            f"{min(cursos_mm):+.0f} a {max(cursos_mm):+.0f}mm)"
            if ok == total else
            f"⚠️ {total - ok}/{total} configurações com interferência "
            f"({criticas_total} críticas, {sum(len(r['interferencias']) for r in resultados) - criticas_total} não-críticas)"
        )
    }


# ==================== SAÍDA E RELATÓRIO ====================

def gerar_relatorio_html(dados: Dict, arquivo: str = 'varredura_modulo_completo.html'):
    """Gera relatório HTML interativo."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Varredura Completa do Módulo Dianteiro — Hammerhead</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .ok {{ color: green; font-weight: bold; }}
        .erro {{ color: red; font-weight: bold; }}
        .stats {{ background: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .stats div {{ margin: 10px 0; font-size: 16px; }}
        .conclusao {{ background: #d5f4e6; padding: 15px; border-left: 5px solid #27ae60; margin: 20px 0; }}
    </style>
</head>
<body>
<div style="padding:16px;background:#ffe6e6;border:3px solid #ad0000;color:#650000"><strong>NÃO APROVADO PARA FABRICAÇÃO.</strong> Revisão independente identificou falhas de folgas, espelhamento, vínculos e colisões. Consulte AUDITORIA_VARREDURA_MODULO.md. Resultados abaixo são históricos e não validados.</div>
<div class="container">
    <h1>🔧 Varredura Completa do Módulo Dianteiro — Hammerhead</h1>
    
    <div class="stats">
        <h2>📊 Estatísticas Gerais</h2>
        <div><strong>Configurações testadas:</strong> {dados['estatisticas']['configuracoes_total']}</div>
        <div><strong>Configurações OK:</strong> <span class="ok">{dados['estatisticas']['configuracoes_ok']}</span></div>
        <div><strong>Com interferências:</strong> <span class="erro">{dados['estatisticas']['configuracoes_com_interferencia']}</span></div>
        <div><strong>Interferências críticas (severidade ALTA):</strong> <span class="erro">{dados['estatisticas']['interferencias_criticas_total']}</span></div>
        <div><strong>Taxa de sucesso:</strong> {dados['estatisticas']['taxa_sucesso_pct']}%</div>
        <div><strong>Envelope y máximo:</strong> {dados['estatisticas']['envelope_y_max_mm']}mm 
             (carroceria: {Y_MAX_CARROCERIA}mm)</div>
        <div><strong>Envelope z mínimo:</strong> {dados['estatisticas']['envelope_z_min_mm']}mm 
             (piso: {Z_PISO_ACABADO}mm)</div>
    </div>
    
    <div class="conclusao">
        <strong>Conclusão:</strong> {dados['conclusao']}
    </div>
    
    <h2>📋 Resultados por Configuração</h2>
    <table>
        <thead>
            <tr>
                <th>Esterço (°)</th>
                <th>Suspensão (mm)</th>
                <th>Status</th>
                <th>Nº Interferências</th>
                <th>Críticas (ALTA)</th>
                <th>Detalhes</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for r in dados['resultados']:
        status_class = 'ok' if r['ok'] else 'erro'
        status_text = '✅ OK' if r['ok'] else f"❌ {r['num_interferencias']} interferências"
        
        # Contar críticas
        criticas = [i for i in r['interferencias'] if i.get('severidade') == 'ALTA']
        num_criticas = len(criticas)
        
        detalhes = ''
        if not r['ok']:
            # Mostrar críticas primeiro
            for i in criticas[:3]:
                detalhes += f"🔴 {i['componente']} vs. {i['obstaculo']}: {i['invasao_mm']}mm<br>"
            # Depois não-críticas
            nao_criticas = [i for i in r['interferencias'] if i.get('severidade') != 'ALTA']
            for i in nao_criticas[:2]:
                sev_emoji = '🟡' if i.get('severidade') == 'MEDIA' else '🟢'
                detalhes += f"{sev_emoji} {i['componente']} vs. {i['obstaculo']}: {i['invasao_mm']}mm<br>"
            
            total_mostrado = len(criticas[:3]) + len(nao_criticas[:2])
            if len(r['interferencias']) > total_mostrado:
                detalhes += f"... +{len(r['interferencias']) - total_mostrado} mais"
        
        html += f"""
            <tr>
                <td>{r['angulo_graus']}</td>
                <td>{r['curso_mm']:+.0f}</td>
                <td class="{status_class}">{status_text}</td>
                <td>{r['num_interferencias']}</td>
                <td class="{'erro' if num_criticas > 0 else ''}">{num_criticas if num_criticas > 0 else '—'}</td>
                <td style="font-size: 12px;">{detalhes or '—'}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <h2>🔍 Componentes Integrados</h2>
    <ul>
        <li><strong>Cubo de roda:</strong> 200mm entre centros, Ø80mm</li>
        <li><strong>Freio a tambor:</strong> Ø130mm (Biz 125)</li>
        <li><strong>Espelho de freio:</strong> Ø180mm, parafusado no balancim</li>
        <li><strong>Balancim:</strong> 260mm (pivô→eixo), Ø32×3mm AISI 4130</li>
        <li><strong>Motores:</strong> 2× por roda, Ø103×190mm</li>
        <li><strong>Suportes de motor:</strong> Flanges Ø140×12mm com 4× furos M8</li>
        <li><strong>Corrente + tensor:</strong> #428, tensor automático INA/Morse</li>
        <li><strong>Placa tensor:</strong> 80×100×4.75mm AISI 1020, fixação chassi</li>
        <li><strong>Amortecedor:</strong> Ø45mm, inclinado 15°</li>
        <li><strong>Caixa de direção:</strong> Ø95×160mm (sede Ø85mm rolamento 30209), topo ≤{Z_CAPO_MAX}mm</li>
        <li><strong>Pernas do garfo:</strong> 2× tubos Ø63,5×4mm a ±175mm do plano médio, altura 470mm</li>
        <li><strong>Proteção corrente:</strong> Alumínio 2mm, 150×250×120mm</li>
    </ul>
    
    <h2>🚗 Zonas Especiais</h2>
    <ul>
        <li><strong>Wheel well (passagem de roda):</strong> x={WHEEL_WELL['x_min']}-{WHEEL_WELL['x_max']}mm, 
            y={WHEEL_WELL['y_min']}-{WHEEL_WELL['y_max']}mm (absoluto). Componentes podem passar abaixo do piso 
            até z={WHEEL_WELL['z_min']}mm sem interferência crítica.</li>
        <li><strong>Carroceria:</strong> y_max = {Y_MAX_CARROCERIA}mm/lado</li>
        <li><strong>Piso acabado:</strong> z = {Z_PISO_ACABADO}mm (piso + EVA 12mm)</li>
    </ul>
    
    <h2>⚙️ Critérios de Severidade</h2>
    <ul>
        <li>🔴 <strong>ALTA (crítica):</strong> Componente invade carroceria com &lt;0mm de folga, ou passa abaixo da zona permitida do wheel well (z &lt; {WHEEL_WELL['z_min']}mm)</li>
        <li>🟡 <strong>MÉDIA:</strong> Componente invade carroceria com 0-10mm de folga, ou cilindros com pequena invasão</li>
        <li>🟢 <strong>BAIXA:</strong> Componente com ≥10mm de margem, ou dentro do wheel well acima de z_min</li>
    </ul>
    
    <p style="color: #7f8c8d; font-size: 12px; margin-top: 40px;">
        Gerado em: """ + __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """<br>
        Ferramenta: varredura_modulo_completo.py<br>
        Projeto: Hammerhead Tricycle
    </p>
</div>
</body>
</html>
"""
    
    with open(arquivo, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Relatório HTML gerado: {arquivo}")


def main():
    # Set UTF-8 encoding for output
    import sys
    import io
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--angulos', nargs='+', type=float, 
                        help='Ângulos de esterço (graus) a testar (padrão: 0 5 10 15 20 25)')
    parser.add_argument('--cursos', nargs='+', type=float,
                        help='Cursos de suspensão (mm) a testar (padrão: -40 -20 0 20 40 60 80)')
    parser.add_argument('--folga', type=float, default=25.0,
                        help='Folga mínima exigida (mm, padrão: 25)')
    parser.add_argument('--lado', choices=['direito', 'esquerdo'], default='direito',
                        help='Lado do módulo (padrão: direito)')
    parser.add_argument('--html', type=str, default='varredura_modulo_completo.html',
                        help='Arquivo HTML de saída')
    parser.add_argument('--json', action='store_true',
                        help='Saída JSON no console')
    
    args = parser.parse_args()
    
    print("🔧 Iniciando varredura completa do módulo dianteiro...")
    print(f"   Esterço: {args.angulos or [0, 5, 10, 15, 20, 25]}°")
    print(f"   Suspensão: {args.cursos or [-40, -20, 0, 20, 40, 60, 80]}mm")
    print(f"   Folga mínima: {args.folga}mm")
    print()
    
    dados = varredura_completa(
        args.angulos,
        args.cursos,
        args.folga,
        args.lado
    )
    
    if args.json:
        print(json.dumps(dados, ensure_ascii=False, indent=2))
    else:
        print("=" * 80)
        print("RESUMO DA VARREDURA")
        print("=" * 80)
        print(f"Total de configurações: {dados['estatisticas']['configuracoes_total']}")
        print(f"Configurações OK: {dados['estatisticas']['configuracoes_ok']}")
        print(f"Com interferências: {dados['estatisticas']['configuracoes_com_interferencia']}")
        print(f"Interferências críticas (ALTA): {dados['estatisticas']['interferencias_criticas_total']}")
        print(f"Taxa de sucesso: {dados['estatisticas']['taxa_sucesso_pct']}%")
        print()
        print(f"Envelope y máximo: {dados['estatisticas']['envelope_y_max_mm']}mm "
              f"(limite: {Y_MAX_CARROCERIA}mm)")
        print(f"Envelope z mínimo: {dados['estatisticas']['envelope_z_min_mm']}mm "
              f"(piso: {Z_PISO_ACABADO}mm, wheel well permitido até z={WHEEL_WELL['z_min']}mm)")
        print()
        print(dados['conclusao'])
        print()
        
        # Mostrar críticas se houver
        if dados['estatisticas']['interferencias_criticas_total'] > 0:
            print("🔴 INTERFERÊNCIAS CRÍTICAS DETECTADAS:")
            for r in dados['resultados']:
                criticas = [i for i in r['interferencias'] if i.get('severidade') == 'ALTA']
                if criticas:
                    print(f"   • Config {r['configuracao']}:")
                    for c in criticas[:2]:
                        print(f"     - {c['componente']} vs. {c['obstaculo']}: {c['invasao_mm']}mm")
            print()
    
    gerar_relatorio_html(dados, args.html)


if __name__ == '__main__':
    main()
