angular.module('group.controllers', ['group.services', 'group.directives',
'common.services', 'auth.services', 'selfie', 'photo.services'])
.controller('CtrlGroupAdd', ['$scope', '$rootScope','$http',
'$location', '$route', 'Auth', 'Group',
    function($scope, $rootScope, $http, $location, $route, Auth, Group) {

        $rootScope.title = 'New group';
        $scope.members = [];
        var auth_promise = Auth.is_authenticated();

        auth_promise.then(function(result){
            if (!result.is_authenticated){
                $window.location.replace("/visitor/");
            }
        });

        $scope.add = function() {
            $scope.data.members = [];
            $scope.members = [];
            var i = 0;
            var member_length = $scope.members.length;
            for (i; i < member_length; i++){
                $scope.data.members.push($scope.members[i].pk);
            }
            Group.save($scope.data, function(success){
                    console.log(success);
                    $location.path('/group/' + success.id + '/manage');
                },
                function(error){
                    $scope.error = error.data;
                }
            );
        };
        $scope.remove_member = function(index){
            $scope.members.splice(index, 1);
        }

    }
])
.controller('CtrlGroupList', ['$scope', '$rootScope','$http', '$window',
'$location', '$routeParams','GetPageLink' , 'Group', 'title', 'my', 'WindowScroll',
    function($scope, $rootScope, $http, $window, $location, $routeParams,
    GetPageLink, Group, title, my, WindowScroll) {

        $rootScope.title = title;
        var query = (my) ? Group.my : Group.query;

        if (my){
            $rootScope.bar = 'verbose';
        }

        $scope.enough = false;

        $scope.r = query($routeParams,
            function(success){

                $scope.enough = success.total > 1 ? false : true;
                $scope.page_link = GetPageLink();
                $scope.page = success.current;
                $scope.prev_pages = [];
                $scope.next_pages = [];
                var i = (success.current - 1 > 5) ? success.current - 5: 1;
                var next_lim = (success.total - success.current > 5) ? 5 + success.current : success.total;
                var j = success.current + 1;
                for (i; i < success.current; i++){ $scope.prev_pages.push(i);}
                for (j; j <= next_lim; j++){ $scope.next_pages.push(j);}

                /* Create an empty array for each group*/
                create_empty_arrays(success);
            },
            function(error){
                for (var e in error.data){
                        $rootScope.alerts.push({ type: 'danger', msg: error.data[e]});
                    }
                    $scope.error = error.data;
            }
        );

        $scope.get_more = function(){
            $scope.page += 1;
            var params = $routeParams;
            params['page'] = $scope.page;
            query(params, function(success){
                    $scope.r.results = $scope.r.results.concat(success.results);
                    $scope.enough = ($scope.page >= $scope.r.total) ? true : false;
                    create_empty_arrays(success);
                },
                function(error){
                    $rootScope.alerts.push({ type: 'danger', msg: error.data[e]});
                }
            );
        };
        WindowScroll($scope, $scope.get_more);

        function create_empty_arrays(obj){
            var k = 0;
            var group_len = obj.results.length;
            for (k; k < group_len; k++){
                var l = 0;
                var len = obj.results[k].overview.length;
                var empty = 3 - len;
                obj.results[k].empty_array = [];
                for (l; l < empty; l++){ obj.results[k].empty_array.push(l);}
            }
        }
    }
])
.controller('CtrlGroupPhotoList', ['$scope', '$rootScope','$http', '$window',
'$location', '$routeParams','GetPageLink' , 'Group', 'IsMember', 'Photo', 'WindowScroll',
    function($scope, $rootScope, $http, $window, $location, $routeParams,
    GetPageLink, Group, IsMember, Photo, WindowScroll) {

        $scope.can_edit = false;
        $rootScope.photo_refer = $location.url();
        $scope.enough = false;

        $scope.group = Group.get({pk: $routeParams.pk},
            function(success){
                if ($rootScope.visitor.pk == success.owner ||
                    IsMember(success.members, $rootScope.visitor.pk)){
                    $scope.can_edit = true;
                }
            }
        );
        var queryParams = {pk: $routeParams.pk, page: $routeParams.page};


        $scope.r = Group.photo_list(queryParams,
            function(success){
                $rootScope.title = 'Groups photo';
                $scope.enough = success.total > 1 ? false : true;
                $scope.page_link = GetPageLink();
                $scope.page = success.current;
                $scope.prev_pages = [];
                $scope.next_pages = [];
                var i = (success.current - 1 > 5) ? success.current - 5: 1;
                var next_lim = (success.total - success.current > 5) ? 5 + success.current : success.total;
                var j = success.current + 1;
                for (i; i < success.current; i++){ $scope.prev_pages.push(i);}
                for (j; j <= next_lim; j++){ $scope.next_pages.push(j);}
            },
            function(error){
                if (typeof error.data == 'object'){
                    for (var e in error.data){
                        $rootScope.alerts.push({ type: 'danger', msg: error.data[e]});
                    }
                    $scope.error = error.data;
                }
            }
        );

        $scope.get_more = function(){
            $scope.page += 1;
            var params = {pk: $routeParams.pk, page: $scope.page};
            Group.photo_list(params, function(success){
                    $scope.r.results = $scope.r.results.concat(success.results);
                    $scope.enough = ($scope.page >= $scope.r.total) ? true : false;
                },
                function(error){
                    if (typeof error.data == 'object'){
                        for (var e in error.data){
                            $rootScope.alerts.push({ type: 'danger', msg: error.data[e]});
                        }
                        $scope.error = error.data;
                    }
                }
            );
        };

        WindowScroll($scope, $scope.get_more);

        $scope.like = function(index, photo_id){
            /*TODO: this is repeats for two times (or even tree) fix!*/
            Photo.like({pk: photo_id},
                function(success){
                    $scope.r.results[index].like_count = success.like_count;
                },
                function(error){
                    $rootScope.alerts.push({ type: 'danger', msg: 'You have like it already!'});
                }
            );
        }
    }
])
.controller('CtrlGroupManage', ['$scope', '$rootScope','$http',
'$location', '$routeParams', '$window', 'Auth', 'Group', 'MultipartForm', 'Tag', 'IsMember', 'RemoveItem',
    function($scope, $rootScope, $http, $location, $routeParams, $window,
    Auth, Group, MultipartForm, Tag, IsMember, RemoveItem) {

        $rootScope.title = 'Update group';
        $scope.is_owner = false;
        $scope.can_edit = false;
        $scope.r = Group.get({pk: $routeParams.pk},
            function(success){
                $scope.data = {title: success.title,
                               description: success.description,
                               is_private: success.is_private};
                if ($rootScope.visitor.pk == success.owner){
                    $scope.is_owner = true;
                }
                if ($rootScope.visitor.pk != success.owner){

                    $rootScope.alerts.push({ type: 'warning',
                        msg: 'You have not enough privileges to manage this group'});
                }
                if (IsMember(success.members, $rootScope.visitor.pk)){
                    $scope.can_edit = true;
                }
            },
            function(error) {
                // TODO: move that func to partials/common, remove duplicates
                for (var e in error.data){
                    $rootScope.alerts.push({ type: 'danger', msg: error.data[e]});
                }
                $scope.error = error.data;
            }
        );
        $scope.random = Math.floor((Math.random()*1000));

        $scope.update_group = function() {
            Group.update({pk: $routeParams.pk}, $scope.data, function(success){
                    $location.path('/group/'+ $routeParams.pk + '/photo');
                },
                function(error){
                    $rootScope.alerts.push({ type: 'danger', msg: 'Error!'});
                }
            );
        };

        $scope.member_remove = function(member_id){
            var confirm = $window.confirm('Are you sure you want to exclude this collaborator?');
            if (confirm){
                Group.member_remove({pk: $routeParams.pk}, {member: member_id},
                    function(success){
                        $rootScope.alerts.push({ type: 'info', msg: 'Collaborator has been excluded.'});
                        RemoveItem($scope.r.members, member_id);
                    },
                    function(error){
                        $rootScope.alerts.push({ type: 'danger', msg: error.data.error });
                    }
                );
            }
        }

        $scope.tag_remove = function(tag_id){
            var confirm = $window.confirm('Are you sure you want to remove this tag?');
            if (confirm){
                Tag.remove({pk: tag_id},
                    function(success){
                        $rootScope.alerts.push({ type: 'info', msg: 'Tag has been removed'});
                        RemoveItem($scope.r.tags, tag_id);
                    },
                    function(error){
                        $rootScope.alerts.push({ type: 'danger', msg: error.data.error });
                    }
                );

            }
        }
        $scope.member_add = function(){
            Group.member_add({pk: $routeParams.pk}, {username: $scope.member},
                function(success){
                    $rootScope.alerts.push({ type: 'info', msg: 'A new member has been added to the group'});
                    $scope.r.members.push(success);
                    $scope.member = '';
                },
                function(error){
                    $rootScope.alerts.push({ type: 'danger', msg: error.data.error });
                }
            );
        }

        $scope.create_tag = function(){
            var confirm = $window.confirm('Are you sure you want to remove this group?');
            if (confirm){
                Group.tag_create({pk: $routeParams.pk}, {title: $scope.tag_title},
                    function(success){
                        $rootScope.alerts.push({ type: 'info', msg: 'A new tag has been created'});
                        $scope.tag_title = '';
                        $scope.r.tags.push(success);
                    },
                    function(error){
                        $rootScope.alerts.push({ type: 'danger', msg: error.data.error });
                    }
                );
            }
        };

        $scope.remove_group = function(){
            var confirm = $window.confirm('Are you sure you want to remove this group?');
            if (confirm){
                Group.remove({pk: $scope.r.id},
                    function(success){
                        $rootScope.alerts.push({ type: 'info', msg: 'Group "'+ $scope.r.title +'" has been removed'});
                        $location.path('/my_groups');
                    },
                    function(error){
                        $rootScope.alerts.push({ type: 'danger', msg: 'Fail'});
                    }
                );
            }
        };
    }
])
.controller('CtrlGroupPhotoAdd', ['$scope', '$rootScope','$http',
'$location', '$routeParams', 'Auth', 'MultipartForm', 'Group', 'IsMember', 'RemoveItem',
    function($scope, $rootScope, $http, $location, $routeParams, Auth, MultipartForm, Group, IsMember, RemoveItem) {

        $rootScope.title = 'New group';
        $scope.can_add = false;
        $scope.wait = false;
        $scope.group = Group.get({pk: $routeParams.pk},
            function(success){
                if ($rootScope.visitor.pk == success.owner ||
                    IsMember(success.members, $rootScope.visitor.pk)){
                    $scope.can_add = true;
                }
            }
        );

        $scope.add = function() {
            $scope.wait = true;
            var url = '/api/v1/group/'+ $scope.group.id +'/photo_create/';
            MultipartForm('POST', '#photo_form', url).then(function(response) {
                $rootScope.alerts.push({ type: 'success', msg: 'Photo has been added to your group!'});
                    $location.path('/group/' + $scope.group.id + '/photo');

                },
                function(error) {
                    $scope.error = error.data;
                    $scope.wait = false;
                }
            );

        };

    }
]);