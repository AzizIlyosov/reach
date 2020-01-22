"""
Operators for running the end-to-end evaluation of Reach.
"""
import os
import tempfile
import json
import gzip

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

from reach.airflow.hook.wellcome_s3_hook import WellcomeS3Hook
from reach.airflow.safe_import import safe_import
from reach.sentry import report_exception
from reach_evaluator import ReachEvaluator

def _get_fuzzy_matches(s3, src_s3_dir_key, organisations):
    """Get all the reach fuzzy matches from all organisations
    and combine into a json.gz.
    """
    task = os.path.split(src_s3_dir_key)[-1]

    fuzzy_matches = []

    for org in organisations:
        src_s3_key = f"{src_s3_dir_key}/{org}/{task}-{org}.json.gz"
        fuzzy_matches.extend(list(_read_json_gz_from_s3(s3, src_s3_key)))

        return fuzzy_matches

def _yield_jsonl_from_gzip(fileobj):
    """ Yield a list of dicts read from gzipped json(l)
    """
    with gzip.GzipFile(mode='rb', fileobj=fileobj) as f:
        for line in f:
            yield json.loads(line)

def _get_span_text(text, span):
    """Get the text that is demarcated by a span in a prodigy dict
    """
    return text[span["start"]:span["end"]]

def _write_json_gz_to_s3(s3, data, key):
    """Write a list of jsons to json.gz on s3
    """
    with tempfile.NamedTemporaryFile(mode='wb') as output_raw_f:
        with gzip.GzipFile(mode='wb', fileobj=output_raw_f) as output_f:
            for item in data:
                output_f.write(json.dumps(item).encode('utf-8'))
                output_f.write(b"\n")

        output_raw_f.flush()
        s3.load_file(
            filename=output_raw_f.name,
            key=key,
            replace=True
        )

def _read_json_gz_from_s3(s3, key):
    """Write a list of jsons to json.gz on s3
    """
    with tempfile.TemporaryFile(mode='rb+') as tf:
        key = s3.get_key(key)
        key.download_fileobj(tf)
        tf.seek(0)

        return list(_yield_jsonl_from_gzip(tf))


class ExtractRefsFromGoldDataOperator(BaseOperator):
    """Extracts references from reference and title annotations.

    The title annotations needs to be re-matched to the reference annotations
    to add in the doc_id. The resulting file can then be sent for matching
    against EPMC.
    """

    template_fields = (
        'refs_s3_key',
        'titles_s3_key',
        'dst_s3_key',
    )

    @apply_defaults
    def __init__(self, refs_s3_key, titles_s3_key, dst_s3_key,
                 aws_conn_id="aws_default", *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.refs_s3_key = refs_s3_key
        self.titles_s3_key = titles_s3_key
        self.dst_s3_key = dst_s3_key
        self.aws_conn_id = aws_conn_id

    @report_exception
    def execute(self, context):
        s3 = WellcomeS3Hook(aws_conn_id=self.aws_conn_id)

        results = []

        # Download and open the two annotated data files.

        refs = _read_json_gz_from_s3(s3, self.refs_s3_key)
        titles = _read_json_gz_from_s3(s3, self.titles_s3_key)

        self.log.info(
            'ExtractRefsFromGoldDataOperator read %d lines from %s',
            len(refs),
            self.refs_s3_key
        )

        self.log.info(
            'ExtractRefsFromGoldDataOperator read %d lines from %s',
            len(titles),
            self.titles_s3_key
        )

        # Create lookup dict mapping input_hash to meta data

        metas = {doc.get('_input_hash'):doc.get('meta') for doc in refs}
        annotated_with_meta = []

        for doc in titles:
            doc["meta"] = metas.get(doc['_input_hash'])
            annotated_with_meta.append(doc)

        # Extract the "Title" and "document_id" from the annotated references

        annotated_titles = []

        for doc in annotated_with_meta:
            doc_hash = None
            meta = doc.get("meta", dict())

            # Get metadata if it exists (this will contain the document hash -
            # the unique id for the downloaded document assigned by Reach.

            if meta:
                doc_hash = meta.get("doc_hash")
            spans = doc.get("spans")

            # Get spans, and create references from them. Note that these spans
            # need to be BI_TITLE, BE_TITLE, i.e. reference level spans, not
            # individual token level spans!

            if spans:
                for span in spans:
                    annotated_titles.append(
                        {
                            "document_id": doc_hash,
                            "Title": _get_span_text(doc["text"], span)
                        }
                    )

        _write_json_gz_to_s3(s3, annotated_titles, key=self.dst_s3_key)

        self.log.info(
            'ExtractRefsFromGoldDataOperator wrote %d lines to %s.',
            len(annotated_titles),
            self.dst_s3_key
        )

        self.log.info(
            'ExtractRefsFromGoldDataOperator: Done extracting refs from '
            'annotated data.'
        )


class EvaluateOperator(BaseOperator):
    """
    Take the output of fuzz-matched-refs operator and evaluates the results
    against a manually labelled gold dataset, returning results in a json
    to s3.

    Args:
        src_s3_key: S3 URL for input
        dst_s3_key: S3 URL for output
    """

    template_fields = (
        'gold_s3_key',
        'reach_s3_key',
        'dst_s3_key',
    )

    @apply_defaults
    def __init__(self, gold_s3_key, reach_s3_key, dst_s3_key, aws_conn_id='aws_default', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gold_s3_key = gold_s3_key
        self.reach_s3_key = reach_s3_key
        self.dst_s3_key = dst_s3_key
        self.aws_conn_id = aws_conn_id

    @report_exception
    def execute(self, context):

        s3 = WellcomeS3Hook(aws_conn_id=self.aws_conn_id)

        results = []

        # Read data from S3
        gold = _read_json_gz_from_s3(s3, self.gold_s3_key)
        reach = _read_json_gz_from_s3(s3, self.reach_s3_key)

        evaluator = ReachEvaluator(gold, reach)
        eval_results = evaluator.eval()

        # Add additional metadata

        eval_results["gold_refs"] = self.gold_s3_key
        eval_results["reach_refs"] = self.reach_s3_key

        # Write the results to S3
        _write_json_gz_to_s3(s3, [eval_results], key=self.dst_s3_key)

        self.log.info(
            'EvaluateOperator: Finished Evaluating Reach matches'
        )

class CombineReachFuzzyMatchesOperator(BaseOperator):
    """ Combine all Reach fuzzy matches into a single file
    """

    template_fields = (
        'organisations',
        'src_s3_dir_key',
        'dst_s3_key',
    )

    @apply_defaults
    def __init__(self, organisations, src_s3_dir_key, dst_s3_key,
                 aws_conn_id="aws_default", *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.organisations = organisations
        self.src_s3_dir_key = src_s3_dir_key
        self.dst_s3_key = dst_s3_key
        self.aws_conn_id = aws_conn_id

    @report_exception
    def execute(self, context):
        s3 = WellcomeS3Hook(aws_conn_id=self.aws_conn_id)

        fuzzy_matches = _get_fuzzy_matches(s3,
            self.src_s3_dir_key, self.organisations)

        self.log.info(
            'CombineReachFuzzyMatchesOperator: read %d lines from %s files',
            len(fuzzy_matches),
            len(self.organisations),
            )

        # Write the results to S3

        _write_json_gz_to_s3(s3, fuzzy_matches, key=self.dst_s3_key)

        self.log.info(
            'CombineReachFuzzyMatchesOperator: wrote %d lines to %s.',
            len(fuzzy_matches),
            self.dst_s3_key
        )
        self.log.info(
            'CombineReachFuzzyMatchesOperator: Done combining reach fuzzy matches.'
        )
