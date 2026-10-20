"""Real template pixels through extracted pure matcher; no native imports/device."""
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]

class ClassRankAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cv2,numpy
        cls.cv2,cls.np=cv2,numpy
        files=sorted((ROOT/'FGO-py/fgoImage/class').glob('*.png'))
        cls.pairs=[list(map(int,p.stem.split('-'))) for p in files]
        cls.images=[cv2.imread(str(p),-1) for p in files]
        tree=ast.parse((ROOT/'FGO-py/fgoDetect.py').read_text())
        base=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='XDetectBase')
        methods=[n for n in base.body if isinstance(n,ast.FunctionDef) and n.name in {'_crop','_loc','_select','getFieldServantClassRank'}]
        images=[(i[:,:,:3],i[:,:,3]) for i in cls.images]
        env=dict(cv2=cv2,numpy=numpy,classImg=(cls.pairs,images),CLASS={125:[[cv2.resize(x,(0,0),fx=1.25,fy=1.25,interpolation=cv2.INTER_CUBIC) for x in item] for item in images]})
        for method in methods:method.decorator_list=[]
        node=ast.ClassDef(name='Detector',bases=[],keywords=[],body=methods,decorator_list=[])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'class_ast','exec'),env)
        cls.Detector=env['Detector']
    def test_new_assets_keep_native_dimensions_and_alpha(self):
        for pair,image in zip(self.pairs,self.images):
            if pair in ([0,3],[2,3],[4,3]):
                self.assertEqual(image.shape,(55,77,4))
                self.assertTrue((image[:,:,3]==0).any());self.assertTrue((image[:,:,3]>0).any())
                # All four native scales must fit every matching region.
                for scale,region in [(75,(63,47)),(93,(85,70)),(100,(85,70)),(125,(104,84))]:
                    h,w=self.cv2.resize(image,None,fx=scale/100,fy=scale/100).shape[:2]
                    self.assertLessEqual(w,region[0]);self.assertLessEqual(h,region[1])
    def test_each_template_preserves_class_and_rank_at_field_scale(self):
        cv2,np=self.cv2,self.np
        for pair,image in zip(self.pairs,self.images):
            d=self.Detector();d.im=np.zeros((720,1280,3),np.uint8)
            icon=cv2.resize(image[:,:,:3],None,fx=1.25,fy=1.25,interpolation=cv2.INTER_CUBIC)
            h,w=icon.shape[:2];d.im[623:623+h,16:16+w]=icon
            self.assertEqual(d.getFieldServantClassRank(0),pair)
    def test_blank_noise_and_occlusion_stay_unknown(self):
        np=self.np;d=self.Detector()
        for im in [np.zeros((720,1280,3),np.uint8),np.full((720,1280,3),255,np.uint8),np.random.default_rng(17).integers(0,256,(720,1280,3),dtype=np.uint8)]:
            d.im=im;self.assertIsNone(d.getFieldServantClassRank(0))
        for pair,image in zip(self.pairs,self.images):
            if pair not in ([0,3],[2,3],[4,3]):continue
            d.im=np.zeros((720,1280,3),np.uint8)
            icon=self.cv2.resize(image[:,:,:3],None,fx=1.25,fy=1.25,interpolation=self.cv2.INTER_CUBIC)
            h,w=icon.shape[:2];d.im[623:623+h,16:16+w]=icon
            d.im[618:702,13:117]=0
            self.assertIsNone(d.getFieldServantClassRank(0))
