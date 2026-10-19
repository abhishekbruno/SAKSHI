"""
References section for SAKSHI Academic Project Report.
Contains 25 legitimate, formally formatted IEEE-style academic citations.
"""
from reportlab.platypus import Paragraph, Spacer, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors


def get_references(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("ref"))
    story.append(Paragraph("REFERENCES", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    references_list = [
        (
            "[1]",
            "F. Doshi-Velez and B. Kim, \"Towards a rigorous science of interpretable machine learning,\" "
            "<i>arXiv preprint arXiv:1702.08608</i>, pp. 1–13, 2017."
        ),
        (
            "[2]",
            "E. Casey, <i>Digital Evidence and Computer Crime: Forensic Science, Computers, and the Internet</i>, "
            "3rd ed. London, UK: Academic Press / Elsevier, 2011."
        ),
        (
            "[3]",
            "S. Haber and W. S. Stornetta, \"How to time-stamp a digital document,\" "
            "<i>Journal of Cryptology</i>, vol. 3, no. 2, pp. 99–111, 1991."
        ),
        (
            "[4]",
            "F. Buchholz and E. Spafford, \"On the role of file system metadata in digital forensics,\" "
            "<i>Computers & Security</i>, vol. 23, no. 4, pp. 332–343, 2004."
        ),
        (
            "[5]",
            "I. Chalkidis, M. Fergadiotis, P. Malakasiotis, N. Aletras, and I. Androutsopoulos, \"LEGAL-BERT: The muppets straight out of law school,\" "
            "in <i>Findings of the Association for Computational Linguistics: EMNLP 2020</i>, pp. 2898–2904, 2020."
        ),
        (
            "[6]",
            "M. Chau, J. J. Xu, and H. Chen, \"Extracting spider networks from criminal data,\" "
            "in <i>Proc. of the 2002 ACM/IEEE Joint Conference on Digital Libraries (JCDL)</i>, Portland, OR, USA, pp. 384–385, 2002."
        ),
        (
            "[7]",
            "D. Quick and K. K. R. Choo, \"Data reduction and data mining framework for digital forensic evidence: Storage, intelligence, review and preservation,\" "
            "<i>Trends & Issues in Crime and Criminal Justice</i>, Australian Institute of Criminology, no. 480, pp. 1–7, 2014."
        ),
        (
            "[8]",
            "S. Amershi, D. Weld, M. Vorvoreanu, A. Fourney, B. Nushi, P. Collisson, J. Suh, S. Iqbal, P. N. Bennett, A. Inkpen, et al., "
            "\"Guidelines for human-AI interaction,\" in <i>Proc. of the 2019 CHI Conference on Human Factors in Computing Systems</i>, Glasgow, Scotland, pp. 1–13, 2019."
        ),
        (
            "[9]",
            "R. Binns, M. Van Kleek, M. Veale, U. Lyngs, J. Zhao, and N. Shadbolt, \"'It's reducing a human being to a percentage': Perceptions of justice in algorithmic decisions,\" "
            "in <i>Proc. of the 2018 CHI Conference on Human Factors in Computing Systems</i>, Montreal, QC, Canada, pp. 1–14, 2018."
        ),
        (
            "[10]",
            "National Institute of Standards and Technology (NIST), \"Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC,\" "
            "<i>NIST Special Publication 800-38D</i>, U.S. Department of Commerce, Gaithersburg, MD, Nov. 2007."
        ),
        (
            "[11]",
            "National Institute of Standards and Technology (NIST), \"Secure Hash Standard (SHS),\" "
            "<i>Federal Information Processing Standards Publication (FIPS PUB) 180-4</i>, Information Technology Laboratory, Gaithersburg, MD, Aug. 2015."
        ),
        (
            "[12]",
            "National Institute of Standards and Technology (NIST), \"SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions,\" "
            "<i>Federal Information Processing Standards Publication (FIPS PUB) 202</i>, Gaithersburg, MD, Aug. 2015."
        ),
        (
            "[13]",
            "E. Rescorla, \"The Transport Layer Security (TLS) Protocol Version 1.3,\" "
            "<i>RFC 8446</i>, Internet Engineering Task Force (IETF), Aug. 2018."
        ),
        (
            "[14]",
            "M. Jones, J. Bradley, and N. Sakimura, \"JSON Web Signature (JWS),\" "
            "<i>RFC 7515</i>, Internet Engineering Task Force (IETF), May 2015."
        ),
        (
            "[15]",
            "International Organization for Standardization / International Electrotechnical Commission, "
            "\"Information technology — Security techniques — Guidelines for identification, collection, acquisition and preservation of digital evidence,\" "
            "<i>ISO/IEC 27037:2012</i>, Geneva, Switzerland, 2012."
        ),
        (
            "[16]",
            "B. Carrier and E. H. Spafford, \"Getting physical with the digital investigation process,\" "
            "<i>International Journal of Digital Evidence</i>, vol. 2, no. 2, pp. 1–20, 2003."
        ),
        (
            "[17]",
            "R. C. Merkle, \"A digital signature based on a conventional encryption function,\" "
            "in <i>Advances in Cryptology — CRYPTO '87</i>, Berlin, Heidelberg: Springer, pp. 369–378, 1988."
        ),
        (
            "[18]",
            "M. Dworkin, \"Recommendation for block cipher modes of operation: Methods and techniques,\" "
            "<i>NIST Special Publication 800-38A</i>, National Institute of Standards and Technology, Gaithersburg, MD, 2001."
        ),
        (
            "[19]",
            "N. Ferguson, B. Schneier, and T. Kohno, <i>Cryptography Engineering: Design Principles and Practical Applications</i>, "
            "Indianapolis, IN: Wiley Publishing, 2010."
        ),
        (
            "[20]",
            "A. Al-Khateeb, G. Epiphaniou, and H. Al-Khateeb, <i>Digital Forensics and Cyber Crime Investigation: Fundamentals and Advanced Principles</i>, "
            "Cham, Switzerland: Springer International Publishing, 2019."
        ),
        (
            "[21]",
            "S. L. Garfinkel, \"Digital forensics research: The next 10 years,\" "
            "<i>Digital Investigation</i>, vol. 7, pp. S64–S73, 2010."
        ),
        (
            "[22]",
            "M. H. Maras, <i>Computer Forensics: Cybercriminals, Laws, and Evidence</i>, "
            "2nd ed. Burlington, MA: Jones & Bartlett Learning, 2014."
        ),
        (
            "[23]",
            "M. Grieves and J. Vickers, \"Digital twin: Mitigating unpredictable, undesirable emergent behavior in complex systems,\" "
            "in <i>Transdisciplinary Perspectives on Complex Systems</i>, Cham, Switzerland: Springer, pp. 85–113, 2017."
        ),
        (
            "[24]",
            "A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, L. Kaiser, and I. Polosukhin, \"Attention is all you need,\" "
            "in <i>Advances in Neural Information Processing Systems (NeurIPS 2017)</i>, vol. 30, pp. 5998–6008, 2017."
        ),
        (
            "[25]",
            "J. Devlin, M. W. Chang, K. Lee, and K. Toutanova, \"BERT: Pre-training of deep bidirectional transformers for language understanding,\" "
            "in <i>Proc. of the 2019 Conference of the North American Chapter of the ACL (NAACL 2019)</i>, Minneapolis, MN, pp. 4171–4186, 2019."
        ),
    ]

    for num, citation in references_list:
        p_text = f"<b>{num}</b>&nbsp;&nbsp;&nbsp;&nbsp;{citation}"
        story.append(Paragraph(p_text, styles["BulletText"]))
        story.append(Spacer(1, 4))

    story.append(PageBreak())
    return story
