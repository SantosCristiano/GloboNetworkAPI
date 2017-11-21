# -*- coding: utf-8 -*-
import logging

from _mysql_exceptions import OperationalError
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q

from networkapi.api_route_map.v4 import exceptions
from networkapi.api_route_map.v4.exceptions import RouteMapAssociatedToPeerGroupException
from networkapi.api_route_map.v4.exceptions import \
    RouteMapAssociatedToRouteMapEntryException
from networkapi.api_route_map.v4.exceptions import \
    RouteMapEntryDuplicatedException
from networkapi.api_route_map.v4.exceptions import RouteMapIsDeployedException
from networkapi.models.BaseModel import BaseModel
from networkapi.util.geral import get_model


class RouteMapEntryAction:
    p = ('P', 'P')
    d = ('D', 'D')
    list_type = (p, d)


class RouteMap(BaseModel):

    id = models.AutoField(
        primary_key=True,
        db_column='id'
    )

    name = models.CharField(
        blank=False,
        max_length=45,
        db_column='name'
    )

    created = models.BooleanField(
        default=False,
        db_column='created'
    )

    log = logging.getLogger('RouteMap')

    class Meta(BaseModel.Meta):
        db_table = u'route_map'
        managed = True

    def _get_route_map_entries(self):
        return self.routemapentry_set.all()

    route_map_entries = property(_get_route_map_entries)

    def _get_route_map_entries_id(self):
        return self.routemapentry_set.all().values_list('id',
                                                        flat=True)

    route_map_entries_id = property(_get_route_map_entries_id)

    def _get_peer_groups_id(self):
        return list(set().union(
            self.peergroup_route_map_in.all().values_list('id', flat=True),
            self.peergroup_route_map_out.all().values_list('id', flat=True),
        ))

    peer_groups_id = property(_get_peer_groups_id)

    def _get_peer_groups(self):
        return list(set().union(
            self.peergroup_route_map_in.all(),
            self.peergroup_route_map_out.all(),
        ))

    peer_groups = property(_get_peer_groups)

    @classmethod
    def get_by_pk(cls, id):
        """Get RouteMap by id.

        :return: RouteMap.

        :raise RouteMapNotFoundError: RouteMap not registered.
        :raise RouteMapError: Failed to search for the RouteMap.
        :raise OperationalError: Lock wait timeout exceeded
        """
        try:
            return RouteMap.objects.get(id=id)
        except ObjectDoesNotExist:
            cls.log.error(u'RouteMap not found. pk {}'.format(id))
            raise exceptions.RouteMapNotFoundError(id)
        except OperationalError:
            cls.log.error(u'Lock wait timeout exceeded.')
            raise OperationalError()
        except Exception:
            cls.log.error(u'Failure to search the RouteMap.')
            raise exceptions.RouteMapError(u'Failure to search the RouteMap.')

    def create_v4(self, route_map):
        """Create RouteMap."""

        self.name = route_map.get('name')

        self.save()

    def update_v4(self, route_map):
        """Update RouteMap."""

        self.name = route_map.get('name')

        if self.created:
            raise RouteMapIsDeployedException(self)

        self.save()

    def delete_v4(self):
        """Delete RouteMap."""

        if self.created:
            raise RouteMapIsDeployedException(self)

        if self.routemapentry_set.count() > 0:
            raise RouteMapAssociatedToRouteMapEntryException(self)

        if self.peergroup_route_map_in.count() > 0 or \
           self.peergroup_route_map_out.count() > 0:
            raise RouteMapAssociatedToPeerGroupException(self)

        super(RouteMap, self).delete()


class RouteMapEntry(BaseModel):

    id = models.AutoField(
        primary_key=True,
        db_column='id'
    )

    action = models.CharField(
        db_column='action',
        max_length=2,
        blank=False,
        choices=RouteMapEntryAction.list_type
    )

    action_reconfig = models.TextField(
        blank=False,
        db_column='action_reconfig'
    )

    order = models.IntegerField(
        db_column='order'
    )

    list_config_bgp = models.ForeignKey(
        'api_list_config_bgp.ListConfigBGP',
        db_column='id_list_config_bgp'
    )

    route_map = models.ForeignKey(
        'api_route_map.RouteMap',
        db_column='id_route_map'
    )

    log = logging.getLogger('RouteMapEntry')

    class Meta(BaseModel.Meta):
        db_table = u'route_map_entry'
        managed = True

    @classmethod
    def get_by_pk(cls, id):
        """Get RouteMapEntry by id.

        :return: RouteMapEntry.

        :raise RouteMapEntryNotFoundError: RouteMapEntry not registered.
        :raise RouteMapEntryError: Failed to search for the RouteMapEntry.
        :raise OperationalError: Lock wait timeout exceeded
        """
        try:
            return RouteMapEntry.objects.get(id=id)
        except ObjectDoesNotExist:
            cls.log.error(u'RouteMapEntry not found. pk {}'.format(id))
            raise exceptions.RouteMapEntryNotFoundError(id)
        except OperationalError:
            cls.log.error(u'Lock wait timeout exceeded.')
            raise OperationalError()
        except Exception:
            cls.log.error(u'Failure to search the RouteMapEntry.')
            raise exceptions.RouteMapEntryError(
                u'Failure to search the RouteMapEntry.')

    def create_v4(self, route_map_entry):
        """Create RouteMapEntry."""

        listconfigbgp_model = get_model('api_list_config_bgp', 'ListConfigBGP')

        self.action = route_map_entry.get('action')
        self.action_reconfig = route_map_entry.get('action_reconfig')
        self.order = route_map_entry.get('order')

        self.list_config_bgp = listconfigbgp_model.get_by_pk(
            route_map_entry.get('list_config_bgp'))
        self.route_map = RouteMap.get_by_pk(route_map_entry.get('route_map'))

        self.validate_route_map_entry()

        self.save()

    def update_v4(self, route_map_entry):
        """Update RouteMapEntry."""

        listconfigbgp_model = get_model('api_list_config_bgp', 'ListConfigBGP')

        self.action = route_map_entry.get('action')
        self.action_reconfig = route_map_entry.get('action_reconfig')
        self.order = route_map_entry.get('order')

        self.list_config_bgp = listconfigbgp_model.get_by_pk(
            route_map_entry.get('list_config_bgp'))
        self.route_map = RouteMap.get_by_pk(route_map_entry.get('route_map'))

        self.validate_route_map_entry()

        self.save()

    def delete_v4(self):
        """Delete RouteMapEntry."""

        super(RouteMapEntry, self).delete()

    def validate_route_map_entry(self):

        # check if already exists route map entry
        route_map_entry = RouteMapEntry.objects.filter(
            Q(list_config_bgp=self.list_config_bgp.id),
            Q(route_map=self.route_map.id),
        )

        if route_map_entry:
            raise RouteMapEntryDuplicatedException(self)
