"""Same-frame layout contract; no screenshots, native imports or device access."""
import ast
import json
from types import SimpleNamespace
import unittest
from test_cards import detector_methods
from test_card_boundaries import evidence_frame


def layout_frame(scores=None,text='rts',back=.99):
    frame=evidence_frame(text=text,score=back)
    node=next(n for n in detector_methods() if n.name=='getCardLayoutEvidence')
    env={};exec(compile(ast.Module(body=[node],type_ignores=[]),'layout_ast','exec'),env)
    frame.getCardLayoutEvidence=lambda:env['getCardLayoutEvidence'](frame)
    frame.im=SimpleNamespace(shape=(720,1280,3))
    frame.tmpl.ARTS=0;frame.tmpl.QUICK=1;frame.tmpl.BUSTER=2
    scores=scores or [[.01,.3,.4]for _ in range(5)]
    frame.calls=[]
    def loc(template,rect):
        frame.calls.append((template,rect))
        return (scores[(rect[0]-80)//257][template],None,None,None)
    frame._loc=loc
    frame.ocr.detect_and_ocr=lambda *a,**k:[SimpleNamespace(text=text,score=.99,box=[[100,450],[150,450],[150,470],[100,470]])]
    return frame


class CardLayoutTest(unittest.TestCase):
    def test_no_complete_words_needed_and_exactly_fifteen_local_matches(self):
        f=layout_frame();r=f.getCardSelectionEvidence()
        self.assertEqual(r['kind'],'selecting');self.assertTrue(r['card_layout']['complete'])
        self.assertEqual(len(f.calls),15)
        self.assertEqual([s['rect'][0]for s in r['card_layout']['slots']],[80,337,594,851,1108])
        self.assertFalse(r['selection_marker_visible'])

    def test_one_glyph_or_full_ocr_word_is_not_a_complete_layout(self):
        for slots in (0,1,4):
            f=layout_frame([[.01,.3,.4]if i<slots else [.4,.5,.6]for i in range(5)],text='Arts')
            self.assertEqual(f.getCardSelectionEvidence()['kind'],'unknown')

    def test_back_button_and_native_conflicts_have_priority(self):
        self.assertEqual(layout_frame(back=.84).getCardSelectionEvidence()['kind'],'unknown')
        for method,kind in [('isNetworkError','dialog'),('isBattleDefeated','defeated'),('isTurnBegin','advanced'),('isBattleFinished','advanced')]:
            f=layout_frame();setattr(f,method,lambda:True)
            self.assertEqual(f.getCardSelectionEvidence()['kind'],kind);self.assertEqual(f.calls,[])

    def test_unchanged_threshold_nonfinite_and_wrong_size_fail_closed(self):
        for error in (.2,.21,float('inf'),float('nan')):
            f=layout_frame([[error,.4,.5]for _ in range(5)])
            r=f.getCardSelectionEvidence();self.assertEqual(r['kind'],'unknown')
            json.dumps(r,allow_nan=False)
        f=layout_frame();f.im.shape=(1440,2560,3)
        self.assertFalse(f.getCardLayoutEvidence()['complete']);self.assertEqual(f.calls,[])

    def test_partial_hand_is_only_stop_evidence_and_disabled_state_survives(self):
        f=layout_frame([[.4,.5,.6]for _ in range(5)],text='1st Attack')
        r=f.getCardSelectionEvidence();self.assertTrue(r['selection_marker_visible'])
        self.assertFalse(r['card_layout']['complete'])
        f=layout_frame();f.getActionDisabled=lambda:dict(face=[None,True,False,False,False],np=[False]*3)
        f.isCardSealed=lambda:[True,True,False,False,False]
        r=f.getCardSelectionEvidence();self.assertEqual(r['action_disabled']['face'][:2],[None,True])
        self.assertEqual(r['unavailable']['face'][:2],[True,True])

    def test_previous_good_frame_cannot_supply_missing_current_layout(self):
        previous=layout_frame();current=layout_frame([[.4,.5,.6]for _ in range(5)])
        self.assertEqual(current.getCardSelectionEvidence(previous=previous)['kind'],'unknown')
