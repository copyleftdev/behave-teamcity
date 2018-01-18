# -*- coding: utf-8 -*-
from behave.formatter.base import Formatter
from behave.model_describe import ModelDescriptor
from teamcity import messages
import os
import time
import behave.reporter.summary

def teamcity_format_summary(statement_type, summary):
    optional_steps = ('untested',)
    parts = []
    tc_parts = []
    tc_log_format = "##teamcity[setParameter name='env.{}_{}' value='{}']\n"
    for status in ('passed', 'failed', 'skipped', 'undefined', 'untested'):
        if status not in summary:
            continue
        counts = summary[status]
        if status in optional_steps and counts == 0:
            # -- SHOW-ONLY: For relevant counts, suppress: untested items, etc.
            continue

        if not parts:
            # -- FIRST ITEM: Add statement_type to counter.
            label = statement_type
            if counts != 1:
                label += 's'
            part = u'%d %s %s' % (counts, label, status) # e.g. 3 features passed
        else:
            part = u'%d %s' % (counts, status)
        parts.append(part)
        if not label.endswith('s'):
            label += 's'
        tc_parts.append(tc_log_format.format(label.upper(), status.upper(), counts))

    standard_behave_log =  ', '.join(parts) + '\n'
    teamcity_log = ''.join(tc_parts)
    return standard_behave_log + teamcity_log

# This is disgusting. But it's better than the alternative, which is trying to decipher
# Python's multiple inheritance in tandem with Behave's formatting options.
# This is a 'monkey-patch', specifically of the format_summary method in Behave's summary.py
# Because this formatter is only used on TeamCity runs, it won't affect local test runs.
behave.reporter.summary.format_summary = teamcity_format_summary


class TeamcityFormatter(Formatter):
    description = "Test"

    def __init__(self, stream_opener, config):
        super(TeamcityFormatter, self).__init__(stream_opener, config)
        self.current_feature = None
        self.current_scenario = None
        self.current_step = None
        self.msg = messages.TeamcityServiceMessages()
        self.flow_id = "Build" + str(time.time())

    def feature(self, feature):
        self.current_feature = feature
        self.current_scenario = None
        self.current_step = None
        self.msg.testSuiteStarted(self.current_feature.name.encode(encoding='ascii', errors='replace'))

    def scenario(self, scenario):
        if self.current_scenario and self.current_scenario.status == "skipped":
            self.msg.testIgnored(self.current_scenario.name.encode(encoding='ascii', errors='replace'))

        self.current_scenario = scenario
        self.current_step = None
        self.msg.testStarted(self.current_scenario.name.encode(encoding='ascii', errors='replace'), captureStandardOutput='false')

    def step(self, step):
        self.current_step = step

    def result(self, step_result):
        text = u'%6s %s ... ' % (step_result.keyword, step_result.name)
        self.msg.progressMessage(text.encode(encoding='ascii', errors='replace'))

        if self.current_scenario.status == "untested":
            return

        status = self.current_scenario.status
        if type(self.current_scenario.status) is not str:
            # Behave 1.2.6 (not released yet) converts status into an enum, but we need to be backwards-compatible
            status = status.name

        if status == "passed":
            self.msg.message('testFinished', name=self.current_scenario.name.encode(encoding='ascii', errors='replace'),
                             duration=str(self.current_scenario.duration), outcome=str(status), framework=os.environ['TEAMCITY_BUILDCONF_NAME'], service=os.environ['TEAMCITY_PROJECT_NAME'], environment=os.environ['SITE'], flowId=self.flow_id)

        if status == "failed":
            name = step_result.name

            error_msg = u"Step failed: {}".format(name.encode(encoding='ascii', errors='replace'))
            if self.current_step.table:
                table = ModelDescriptor.describe_table(self.current_step.table, None)
                error_msg = u"{}\nTable:\n{}".format(error_msg, table)

            if self.current_step.text:
                text = ModelDescriptor.describe_docstring(self.current_step.text, None)
                error_msg = u"{}\nText:\n{}".format(error_msg, text)

            error_details = step_result.error_message

            self.msg.testFailed(self.current_scenario.name.encode(encoding='ascii', errors='replace'), message=error_msg, details=error_details)
            self.msg.message('testFinished', name=self.current_scenario.name.encode(encoding='ascii', errors='replace'),
                             duration=str(self.current_scenario.duration), outcome=str(status), framework=os.environ['TEAMCITY_BUILDCONF_NAME'], service=os.environ['TEAMCITY_PROJECT_NAME'], environment=os.environ['SITE'], flowId=self.flow_id)

    def eof(self):
        if self.current_scenario and self.current_scenario.status == "skipped":  # Check the last scenario in a feature, as scenario() won't
            self.msg.testIgnored(self.current_scenario.name.encode(encoding='ascii', errors='replace'))
        self.msg.testSuiteFinished(self.current_feature.name.encode(encoding='ascii', errors='replace'))
