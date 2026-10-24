from fractions import Fraction
import math
from contextlib import nullcontext
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from physics_timing import clock, bracket, interpolate
from physics_backend_example import build_inputs
import physics_backends as physics

class TimingTests(unittest.TestCase):
    def test_exact_ntsc_terminal_brackets_without_drift(self):
        world,_=build_inputs(backend='pybullet')
        world['fps']=dict(numerator=30000,denominator=1001)
        value=clock(world)
        self.assertEqual(value['last_sample_time'],dict(numerator=1001,denominator=625))
        self.assertEqual(value['solver_steps'],385)
        self.assertEqual(value['computed_terminal_time'],dict(numerator=77,denominator=48))
        self.assertEqual(bracket(Fraction(1001,30000),Fraction(1,240)),(8,9,Fraction(1,125)))

    def test_retained_predecessor_caches_remain_hash_verified(self):
        root=Path(__file__).resolve().parents[1]/'tests/results/physics-backends-20261024'
        for backend in ['blender','pybullet']:
            report=physics.verify_cache(root/(backend+'-demo/cache'))
            self.assertEqual(report['status'],'hash-and-contract-verified')

    def test_quaternion_shortest_arc_and_endpoints(self):
        a=dict(id='x',translation=[0,0,0],rotation=[0,0,0,1])
        b=dict(id='x',translation=[2,0,0],rotation=[0,0,0,-1])
        self.assertEqual(interpolate(a,b,Fraction(1,2))['translation'],[1,0,0])
        self.assertEqual(interpolate(a,b,Fraction(1,2))['rotation'],[0,0,0,1])

    def test_backend_restriction_and_stability_are_explicit(self):
        world,_=build_inputs()
        world['fps']=dict(numerator=30000,denominator=1001)
        with self.assertRaises(physics.BackendError):physics.BlenderBackend('/missing').validate_scene(world)
        world['solver']['backend']='pybullet'
        report=physics.PyBulletBackend('/missing').validate_scene(world)
        self.assertEqual(report['timing']['effective_solver_step'],dict(numerator=1,denominator=240))
        world['solver']['stability']=dict(continuous_collision_detection=True)
        with self.assertRaises(physics.BackendError) as raised:physics.PyBulletBackend('/missing').validate_scene(world)
        self.assertEqual(raised.exception.report['code'],'PHYSICS_STABILITY_UNSUPPORTED')

@unittest.skipUnless(os.environ.get('HATCH_PHYSICS_BACKEND_TEST')=='1','Explicit real solver gate')
class NativeTimingTests(unittest.TestCase):
    def test_real_blender_integer_and_ntsc_effective_steps(self):
        with tempfile.TemporaryDirectory(prefix='hatch-blender-timing-') as directory:
            for p,q,denominator in [(24,1,240),(30000,1001,240000)]:
                backend=physics.BlenderBackend(os.environ['HATCH_BLENDER'])
                world,payloads=build_inputs()
                world['fps']=dict(numerator=p,denominator=q)
                world['solver']['fixed_step']=dict(numerator=q,denominator=denominator)
                prepared=backend.prepare(world,payloads)
                try:
                    result=backend.simulate(prepared)
                    destination=Path(directory)/str(p)
                    backend.bake(result,destination)
                    self.assertEqual(physics.verify_cache(destination)['sample_count'],49)
                    for frame in range(1,7):
                        sample=physics.inspect_cache(destination,frame)
                        expected=3-9.81*(frame*q/p)**2/2
                        self.assertLess(abs(sample['bodies'][0]['translation'][1]-expected),.03)
                        self.assertEqual(sample['sampling']['source'],'direct solved state')
                finally:backend.cleanup(prepared)

    def test_real_fractional_rates_analytic_and_pinned_repeat(self):
        records=[]
        target=os.environ.get('HATCH_TIMING_EVIDENCE')
        retained=Path(target).parent/'artifacts' if target else None
        if retained:retained.mkdir(parents=True,exist_ok=False)
        with (nullcontext(str(retained)) if retained else tempfile.TemporaryDirectory(prefix='hatch-timing-oracles-')) as directory:
            for p,q in [(24,1),(30000,1001),(47,2)]:
                outputs=[]
                for repeat in range(2):
                    backend=physics.PyBulletBackend(os.environ['HATCH_PYBULLET_PYTHON'])
                    world,payloads=build_inputs(backend='pybullet')
                    world['fps']=dict(numerator=p,denominator=q)
                    world['solver']['substeps']=2
                    world['solver']['stability']=dict(contact_penetration_tolerance=.001,max_linear_velocity=20,max_angular_velocity=20)
                    prepared=backend.prepare(world,payloads)
                    try:
                        result=backend.simulate(prepared)
                        destination=Path(directory)/f'{p}-{q}-{repeat}'
                        backend.bake(result,destination)
                        self.assertEqual(physics.verify_cache(destination)['sample_count'],49)
                        values=physics.parse((destination/'states.json').read_bytes())
                        maximum=0.
                        dt=Fraction(1,480)
                        for frame in range(1,7):
                            t=Fraction(frame*q,p)
                            coordinate=t/dt;n=math.floor(coordinate);a=float(coordinate-n)
                            expected=3-9.81*float(dt)**2*((1-a)*n*(n+1)+a*(n+1)*(n+2))/2
                            observed=values['samples'][frame]['bodies'][0]['translation'][1]
                            maximum=max(maximum,abs(expected-observed))
                            self.assertLess(abs(expected-observed),1e-9)
                            # Also bound numerical integration error against continuous free fall.
                            self.assertLess(abs(observed-(3-9.81*float(t)**2/2)),.004)
                        sought=physics.inspect_time(destination,Fraction(q,2*p))
                        self.assertEqual(sought['bracket_frames'],[0,1])
                        with self.assertRaises(physics.BackendError):physics.inspect_time(destination,Fraction(49*q,p))
                        outputs.append(values)
                        records.append(dict(rate=[p,q],repeat=repeat,discrete_euler_max_error=maximum,
                            continuous_tolerance=.004,timing=clock(world),backend=result.backend,usage=result.usage,
                            hardware=physics.hardware(),solver=world['solver'],gravity=world['gravity'],materials=world['materials'],
                            cache=physics.verify_cache(destination),states_sha256=physics.digest((destination/'states.json').read_bytes())))
                    finally:backend.cleanup(prepared)
                self.assertEqual(outputs[0],outputs[1])
            target=os.environ.get('HATCH_TIMING_EVIDENCE')
            if target:Path(target).write_bytes(physics.canonical(dict(scope='real PyBullet; pinned same-environment paired runs only',records=records)))
