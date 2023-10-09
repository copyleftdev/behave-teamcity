# -*- coding: utf-8 -*-
from behave.formatter.base import Formatter
from behave.model_describe import ModelDescriptor
from teamcity import messages
import os
import time
import behave.reporter.summary


class TeamCitySummaryFormatter:
    @staticmethod
    def format_summary(statement_type, summary):
        optional_steps = ('untested',)
        parts = []
        tc_parts = []
        tc_log_format = "##teamcity[setParameter name='env.{}_{}' value='{}']\n"
        for status in ('passed', 'failed', 'skipped', 'undefined', 'untested'):
            if status not in summary:
                continue
            counts = summary[status]
            if status in optional_steps and counts == 0:
                continue
            label = statement_type
            if counts != 1:
                label += 's'
            part = u'%d %s %s' % (counts, label, status)
            parts.append(part)
            if not label.endswith('s'):
                label += 's'
            tc_parts.append(tc_log_format.format(label.upper(), status.upper(), counts))
        standard_behave_log = ', '.join(parts) + '\n'
        teamcity_log = ''.join(tc_parts)
        return standard_behave_log + teamcity_log


# Monkey-patch Behave's format_summary method with the TeamCity version
behave.reporter.summary.format_summary = TeamCitySummaryFormatter.format_summary


class TeamcityFormatter(Formatter):
    description = "Test"

    def __init__(self, stream_opener, config):
        super(TeamcityFormatter, self).__init__(stream_opener, config)
        self.msg = messages.TeamcityServiceMessages()
        self.flow_id = "Build" + str(time.time())
        self._reset_currents()

    def _reset_currents(self):
        self.current_feature = None
        self.current_scenario = None
        self.current_step = None

    def feature(self, feature):
        self._reset_currents()
        self.current_feature = feature
        self.msg.testSuiteStarted(self.current_feature.name.encode(encoding='ascii', errors='replace'))

    def scenario(self, scenario):
        self._check_and_report_skipped_scenario()
        self.current_scenario = scenario
        self.msg.testStarted(
            self.current_scenario.name.encode(encoding='ascii', errors='replace'), captureStandardOutput='false')

    def _check_and_report_skipped_scenario(self):
        if self.current_scenario and self.current_scenario.status == "skipped":
            self.msg.testIgnored(self.current_scenario.name.encode(encoding='ascii', errors='replace'))

    def step(self, step):
        self.current_step = step

    def result(self, step_result):
        text = u'%6s %s ... ' % (step_result.keyword, step_result.name)
        self.msg.progressMessage(text.encode(encoding='ascii', errors='replace'))
        self._process_scenario_result(step_result)

    def _process_scenario_result(self, step_result):
        if self.current_scenario.status == "untested":
            return
        status = self._get_scenario_status_name()
        if status == "failed":
            self._report_failed_scenario(step_result)
        self._finalize_scenario_report(status)

    def _get_scenario_status_name(self):
        status = self.current_scenario.status
        if type(status) is not str:  # Backward compatibility for future Behave versions
            status = status.name
        return status

    def _report_failed_scenario(self, step_result):
        error_msg = self._compose_error_message(step_result)
        error_details = step_result.error_message.encode(encoding='ascii', errors='replace')
        self.msg.testFailed(
            self.current_scenario.name.encode(encoding='ascii', errors='replace'),
            message=error_msg,
            details=error_details
        )

    def _compose_error_message(self, step_result):
        name = step_result.name
        error_msg = u"Step failed: {}".format(name.encode(encoding='ascii', errors='replace'))
        if self.current_step.table:
            table = ModelDescriptor.describe_table(self.current_step.table, None)
            error_msg = u"{}\nTable:\n{}".format(error_msg, table)
        if self.current_step.text:
            text = ModelDescriptor.describe_docstring(self.current_step.text, None)
            error_msg = u"{}\nText:\n{}".format(error_msg, text).encode(encoding='ascii', errors='replace')
        return error_msg

    def _finalize_scenario_report(self, status):
        self.msg.message(
            'testFinished',
            name=self.current_scenario.name.encode(encoding='ascii', errors='replace'),
            duration=str(self.current_scenario.duration),
            outcome=status,
            framework=os.environ['TEAMCITY_BUILDCONF_NAME'],
            service=os.environ['TEAMCITY_PROJECT_NAME'],
            environment=os.environ['SITE'],
            flowId=self.flow_id
        )

    def eof(self):
        self._check_and_report_skipped_scenario()
        self.msg.testSuiteFinished(self.current_feature.name.encode(encoding='ascii', errors='replace'))
