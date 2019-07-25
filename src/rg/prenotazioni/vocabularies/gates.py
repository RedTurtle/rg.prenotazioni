# -*- coding: utf-8 -*-
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm


@implementer(IVocabularyFactory)
class GatesVocabulary(object):
    def __call__(self, context):
        """
        Return all the gates defined in the PrenotazioniFolder
        """
        gates = context.getGates()
        return SimpleVocabulary(
            [
                SimpleTerm(gate.decode("utf8"), str(i), gate.decode("utf8"))
                for i, gate in enumerate(gates)
            ]
        )


GatesVocabularyFactory = GatesVocabulary()
